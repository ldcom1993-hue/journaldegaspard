#!/usr/bin/env python3
"""Enrich character data with teams and techniques from Captain Tsubasa Fandom."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fandom.client import (
    fetch_category_titles,
    fetch_intro_extract,
    fetch_page_links,
    fetch_page_wikitext,
)

from fandom.extract_teams import (
    extract_team_candidates_from_page_links,
    extract_teams_from_infobox,
)

from fandom.extract_techniques import (
    build_technique_to_users_map,
    extract_techniques_from_infobox,
    fetch_technique_titles_from_categories,
)

from fandom.normalize import (
    classify_team,
    extract_infobox_fields,
    infer_parent_team,
    normalize_entity_name,
    slugify,
)

from fandom.relations import (
    character_ref,
    entity_ref,
    sort_entities,
)

from fandom.writers import safe_write_non_empty_list


PERSONNAGES_JSON = Path("assets/data/personnages.json")
EQUIPES_JSON = Path("assets/data/equipes.json")
TECHNIQUES_JSON = Path("assets/data/techniques.json")

TEAM_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
OPPONENT_CONTEXT_PATTERNS = (
    r"\bvs\.?\b",
    r"\bagainst\b",
    r"\bmatch(?:es)?\b",
    r"\bwon\b",
    r"\blost\b",
    r"\bdefeated\b",
    r"\bdefeat(?:ed)?\b",
)

COUNTRY_ALIASES = {
    "japan": "japan",
    "japanese": "japan",
    "brazil": "brazil",
    "brazilian": "brazil",
    "argentina": "argentina",
    "argentinian": "argentina",
    "france": "france",
    "french": "france",
    "germany": "germany",
    "german": "germany",
    "italy": "italy",
    "italian": "italy",
    "spain": "spain",
    "spanish": "spain",
    "netherlands": "netherlands",
    "dutch": "netherlands",
    "thailand": "thailand",
    "thai": "thailand",
    "sweden": "sweden",
    "swedish": "sweden",
    "uruguay": "uruguay",
    "england": "england",
    "mexico": "mexico",
    "portugal": "portugal",
}

TEAM_PAGE_CACHE: dict[str, str] = {}


# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------

def load_personnages() -> list[dict[str, Any]]:
    with PERSONNAGES_JSON.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise RuntimeError("assets/data/personnages.json must contain a list")

    return [entry for entry in payload if isinstance(entry, dict)]


def dedupe_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}

    for ref in refs:
        slug = str(ref.get("slug", "")).strip()
        if not slug:
            continue

        previous = unique.get(slug)
        if not previous:
            unique[slug] = ref
            continue

        prev_confidence = str(previous.get("confidence", "medium"))
        new_confidence = str(ref.get("confidence", "medium"))

        if TEAM_CONFIDENCE_ORDER.get(new_confidence, 0) >= TEAM_CONFIDENCE_ORDER.get(prev_confidence, 0):
            unique[slug] = ref

    return sort_entities(list(unique.values()))


def fetch_team_wikitext_cached(team_name: str) -> str:
    if team_name in TEAM_PAGE_CACHE:
        return TEAM_PAGE_CACHE[team_name]

    try:
        team_wikitext = fetch_page_wikitext(team_name)
    except Exception:
        team_wikitext = ""

    TEAM_PAGE_CACHE[team_name] = team_wikitext
    return team_wikitext


def validate_team_membership(team_name: str, character_name: str) -> bool:
    """
    Validate that the team page actually references the character.
    This eliminates most opponent teams.
    """
    team_wikitext = fetch_team_wikitext_cached(team_name)
    if not team_wikitext:
        return False
    return character_name.lower() in team_wikitext.lower()


def normalize_country(value: str) -> str:
    lowered = normalize_entity_name(value).lower()
    tokens = re.findall(r"[a-z]+", lowered)
    for token in tokens:
        mapped = COUNTRY_ALIASES.get(token)
        if mapped:
            return mapped
    return ""


def infer_team_country(team_name: str) -> str:
    lowered = normalize_entity_name(team_name).lower()
    for alias, canonical in COUNTRY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            return canonical
    return ""


def is_opponent_context_only(team_name: str, character_wikitext: str) -> bool:
    if not character_wikitext:
        return False

    normalized_team = normalize_entity_name(team_name)
    if not normalized_team:
        return False

    pattern = re.compile(rf"(.{{0,80}}\b{re.escape(normalized_team)}\b.{{0,80}})", re.IGNORECASE)
    snippets = pattern.findall(character_wikitext)

    if not snippets:
        return False

    opponent_hits = 0

    for snippet in snippets:
        lowered = snippet.lower()
        if any(re.search(context_pattern, lowered) for context_pattern in OPPONENT_CONTEXT_PATTERNS):
            opponent_hits += 1

    return opponent_hits == len(snippets)


def infer_team_confidence(
    *,
    team_name: str,
    character_name: str,
    character_wikitext: str,
    source: str,
    character_nationality: str,
) -> str:
    if source == "infobox":
        return "high"

    roster_validated = validate_team_membership(team_name, character_name)
    if roster_validated:
        return "medium"

    confidence = "low"

    if is_opponent_context_only(team_name, character_wikitext):
        return "low"

    team_classification = classify_team(team_name)
    if team_classification["type"] == "national" and team_classification["age_category"] in ("youth", "olympic", "adult"):
        team_country = infer_team_country(team_name)
        player_country = normalize_country(character_nationality)

        if team_country and player_country and team_country != player_country:
            return "low"

    return confidence


# ------------------------------------------------------------
# Main pipeline
# ------------------------------------------------------------

def main() -> None:

    personnages = load_personnages()

    if not personnages:
        raise RuntimeError("No characters available for enrichment")

    category_titles = fetch_category_titles("Category:Characters")

    title_by_slug = {
        slugify(title.split("/", 1)[0].strip()):
        title.split("/", 1)[0].strip()
        for title in category_titles
    }

    known_character_titles = set(title_by_slug.values())

    team_links_by_character: dict[str, list[dict[str, Any]]] = {}
    technique_links_by_character: dict[str, list[str]] = {}

    print(f"[info] loaded {len(personnages)} characters")
    print(f"[info] found {len(title_by_slug)} Fandom character titles")

    # ------------------------------------------------------------
    # Extract teams and techniques
    # ------------------------------------------------------------

    for record in personnages:

        slug = str(record.get("slug", "")).strip()

        if not slug:
            continue

        title = title_by_slug.get(slug)

        if not title:
            continue

        try:
            wikitext = fetch_page_wikitext(title)
            page_links = fetch_page_links(title)
        except RuntimeError as exc:
            print(f"[warn] skip fetch for {slug}: {exc}")
            continue

        infobox = extract_infobox_fields(wikitext)

        extracted_team_refs: list[dict[str, Any]] = []

        character_nationality = str(record.get("nationality", "")).strip()

        for team in extract_teams_from_infobox(infobox):
            extracted_team_refs.append(
                {
                    "name": team,
                    "confidence": infer_team_confidence(
                        team_name=team,
                        character_name=title,
                        character_wikitext=wikitext,
                        source="infobox",
                        character_nationality=character_nationality,
                    ),
                }
            )

        if not extracted_team_refs:
            team_candidates = extract_team_candidates_from_page_links(
                page_links,
                known_character_titles,
            )

            for team in team_candidates:
                extracted_team_refs.append(
                    {
                        "name": team,
                        "confidence": infer_team_confidence(
                            team_name=team,
                            character_name=title,
                            character_wikitext=wikitext,
                            source="page_links",
                            character_nationality=character_nationality,
                        ),
                    }
                )

        if extracted_team_refs:
            team_links_by_character[slug] = dedupe_refs(
                [
                    {
                        **entity_ref(team_ref["name"], "equipe"),
                        "confidence": team_ref["confidence"],
                    }
                    for team_ref in extracted_team_refs
                ]
            )

        techniques = extract_techniques_from_infobox(infobox)

        if techniques:
            technique_links_by_character[slug] = techniques

    # ------------------------------------------------------------
    # Techniques fallback via categories
    # ------------------------------------------------------------

    technique_titles = fetch_technique_titles_from_categories()

    technique_to_users = build_technique_to_users_map(
        technique_titles,
        known_character_titles,
    )

    for technique_title, user_titles in technique_to_users.items():

        technique_name = normalize_entity_name(technique_title)

        if not technique_name or not user_titles:
            continue

        for user_title in user_titles:

            user_slug = slugify(user_title)

            technique_links_by_character.setdefault(user_slug, [])

            if technique_name not in technique_links_by_character[user_slug]:
                technique_links_by_character[user_slug].append(technique_name)

    # ------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------

    characters_with_teams = sum(1 for v in team_links_by_character.values() if v)
    characters_with_techniques = sum(1 for v in technique_links_by_character.values() if v)

    print(f"[info] characters with teams extracted: {characters_with_teams}")
    print(f"[info] characters with techniques extracted: {characters_with_techniques}")

    # ------------------------------------------------------------
    # Build entities payload
    # ------------------------------------------------------------

    teams_payload: dict[str, dict[str, Any]] = {}
    techniques_payload: dict[str, dict[str, Any]] = {}

    for record in personnages:

        slug = str(record.get("slug", "")).strip()

        if not slug:
            continue

        linked_team_refs = team_links_by_character.get(slug, [])

        linked_technique_refs = [
            entity_ref(t, "technique")
            for t in technique_links_by_character.get(slug, [])
        ]

        teams_initial = dedupe_refs(linked_team_refs)

        filtered_team_refs: list[dict[str, Any]] = []

        character_pointer = character_ref(record)

        # ----------------------------
        # Teams
        # ----------------------------

        for team_ref in teams_initial:
            confidence = str(team_ref.get("confidence", "low"))

            if confidence not in ("high", "medium"):
                continue

            classification = classify_team(team_ref["name"] or team_ref["slug"])

            if classification["type"] == "competition":
                continue

            filtered_team_refs.append(team_ref)

            team_slug = team_ref["slug"]

            if team_slug not in teams_payload:
                parent_team = infer_parent_team(team_ref["name"])
                teams_payload[team_slug] = {
                    "slug": team_ref["slug"],
                    "name": team_ref["name"],
                    "type": classification["type"],
                    "age_category": classification["age_category"],
                    "parent_team": parent_team,
                    "confidence": confidence,
                    "url": team_ref["url"],
                    "description": "",
                    "image": "",
                    "players": [],
                }

            existing_confidence = str(teams_payload[team_slug].get("confidence", "low"))
            if TEAM_CONFIDENCE_ORDER.get(confidence, 0) > TEAM_CONFIDENCE_ORDER.get(existing_confidence, 0):
                teams_payload[team_slug]["confidence"] = confidence

            teams_payload[team_slug]["players"].append(character_pointer)

        record["teams"] = dedupe_refs(filtered_team_refs)

        # ----------------------------
        # Techniques
        # ----------------------------

        record["techniques"] = dedupe_refs(linked_technique_refs)

        for technique_ref in record["techniques"]:

            technique_slug = technique_ref["slug"]

            if technique_slug not in techniques_payload:

                techniques_payload[technique_slug] = {
                    "slug": technique_ref["slug"],
                    "name": technique_ref["name"],
                    "url": technique_ref["url"],
                    "description": "",
                    "image": "",
                    "users": [],
                }

            techniques_payload[technique_slug]["users"].append(character_pointer)

    # ------------------------------------------------------------
    # Final JSON
    # ------------------------------------------------------------

    equipes = sort_entities(
        [
            {
                **team,
                "players": dedupe_refs(team.get("players", [])),
            }
            for team in teams_payload.values()
        ]
    )

    techniques = sort_entities(
        [
            {
                **technique,
                "users": dedupe_refs(technique.get("users", [])),
            }
            for technique in techniques_payload.values()
        ]
    )

    # fetch technique descriptions
    for technique in techniques:
        try:
            technique["description"] = fetch_intro_extract(technique["name"])
        except RuntimeError:
            technique["description"] = ""

    personnages_sorted = sorted(
        personnages,
        key=lambda entry: (
            int(entry.get("popularity", 999)),
            str(entry.get("name", "")).lower(),
        ),
    )

    safe_write_non_empty_list(
        EQUIPES_JSON,
        equipes,
        minimum_items=1,
        label="equipes.json",
    )

    safe_write_non_empty_list(
        TECHNIQUES_JSON,
        techniques,
        minimum_items=1,
        label="techniques.json",
    )

    safe_write_non_empty_list(
        PERSONNAGES_JSON,
        personnages_sorted,
        minimum_items=50,
        label="personnages.json",
    )

    print(f"[ok] wrote {len(equipes)} teams")
    print(f"[ok] wrote {len(techniques)} techniques")
    print(f"[ok] updated {len(personnages_sorted)} characters")


if __name__ == "__main__":
    main()
