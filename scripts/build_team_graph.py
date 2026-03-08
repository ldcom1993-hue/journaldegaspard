#!/usr/bin/env python3
"""Rebuild clean team ↔ player relations from team pages and categories.

Usage:
    python scripts/build_team_graph.py

This script:
- reads assets/data/personnages.json
- discovers team pages from Fandom categories
- extracts players from team pages
- classifies teams
- rewrites assets/data/equipes.json
- rewrites personnages.json teams from validated rosters only

It is designed to run AFTER sync_entities.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fandom.client import fetch_category_titles, fetch_page_wikitext
from fandom.normalize import classify_team, infer_parent_team, normalize_entity_name, slugify
from fandom.relations import entity_ref, sort_entities
from fandom.writers import safe_write_non_empty_list

PERSONNAGES_JSON = Path("assets/data/personnages.json")
EQUIPES_JSON = Path("assets/data/equipes.json")

TEAM_CATEGORY_CANDIDATES = (
    "Category:Teams",
    "Category:Junior Youth Teams",
    "Category:Middle School Teams",
    "Category:High School Teams",
    "Category:Professional Teams",
    "Category:National Teams",
)

PLAYER_SECTION_KEYWORDS = (
    "players",
    "members",
    "team members",
    "member",
    "current squad",
    "former players",
    "notable players",
)

# Sections to ignore when scanning whole page fallback
IGNORE_SECTION_KEYWORDS = (
    "gallery",
    "trivia",
    "notes",
    "external links",
    "etymology",
    "techniques",
    "history",
    "matches",
    "match",
)

LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
HEADING_RE = re.compile(r"^(=+)\s*(.*?)\s*\1\s*$", re.MULTILINE)


def load_json_list(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise RuntimeError(f"{path} must contain a list")
    return [item for item in payload if isinstance(item, dict)]


def normalize_title(value: str) -> str:
    return normalize_entity_name(value).replace("_", " ").strip()


def extract_links(text: str) -> list[str]:
    links: list[str] = []
    for raw in LINK_RE.findall(text or ""):
        title = raw.split("|", 1)[0].split("#", 1)[0].strip()
        if not title:
            continue
        links.append(normalize_title(title))
    return links


def split_sections(wikitext: str) -> list[tuple[str, str]]:
    """Return list of (heading, content)."""
    matches = list(HEADING_RE.finditer(wikitext or ""))
    if not matches:
        return [("", wikitext or "")]

    sections: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        heading = normalize_title(match.group(2))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(wikitext)
        content = wikitext[start:end]
        sections.append((heading, content))
    return sections


def is_player_section(heading: str) -> bool:
    lowered = heading.lower()
    return any(keyword in lowered for keyword in PLAYER_SECTION_KEYWORDS)


def is_ignored_section(heading: str) -> bool:
    lowered = heading.lower()
    return any(keyword in lowered for keyword in IGNORE_SECTION_KEYWORDS)


def build_character_indexes(personnages: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    by_slug: dict[str, dict[str, Any]] = {}
    name_to_slug: dict[str, str] = {}

    def register(name: str, slug: str) -> None:
        normalized = normalize_title(name)
        if normalized and normalized not in name_to_slug:
            name_to_slug[normalized] = slug

    for record in personnages:
        slug = str(record.get("slug", "")).strip()
        if not slug:
            continue

        by_slug[slug] = record

        name = str(record.get("name", "")).strip()
        japanese = str(record.get("japaneseName", "")).strip()

        name_split = record.get("nameSplit") if isinstance(record.get("nameSplit"), dict) else {}
        latin = str(name_split.get("latin", "")).strip()
        kanji = str(name_split.get("kanji", "")).strip()

        for candidate in (name, japanese, latin, kanji):
            if candidate:
                register(candidate, slug)

    return by_slug, name_to_slug


def discover_team_titles() -> list[str]:
    titles: list[str] = []

    for category in TEAM_CATEGORY_CANDIDATES:
        try:
            fetched = fetch_category_titles(category)
        except Exception:
            continue

        for title in fetched:
            normalized = normalize_title(title.split("/", 1)[0])
            if not normalized:
                continue
            if normalized not in titles:
                titles.append(normalized)

    return titles


def extract_players_from_team_page(team_title: str, name_to_slug: dict[str, str]) -> list[str]:
    """Extract players from team page using player sections first, then page-wide fallback."""
    try:
        wikitext = fetch_page_wikitext(team_title)
    except Exception:
        return []

    found_slugs: list[str] = []
    seen: set[str] = set()

    sections = split_sections(wikitext)

    # 1) Strong signal: player/member sections
    candidate_sections = [content for heading, content in sections if is_player_section(heading)]

    # 2) Fallback: use non-ignored sections if dedicated player section is absent
    if not candidate_sections:
        candidate_sections = [content for heading, content in sections if not is_ignored_section(heading)]

    for section_text in candidate_sections:
        for linked_title in extract_links(section_text):
            slug = name_to_slug.get(linked_title)
            if not slug or slug in seen:
                continue
            seen.add(slug)
            found_slugs.append(slug)

    return found_slugs


def build_team_payload(
    team_name: str,
    player_slugs: list[str],
    personnages_by_slug: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    classification = classify_team(team_name)

    if classification["type"] == "competition":
        return None

    team_ref = entity_ref(team_name, "equipe")

    players = []
    for slug in player_slugs:
        record = personnages_by_slug.get(slug)
        if not record:
            continue
        players.append(
            {
                "slug": slug,
                "name": str(record.get("name", "")).strip() or slug,
                "url": f"/univers/olive-et-tom/personnage.html?slug={slug}",
            }
        )

    return {
        "slug": team_ref["slug"],
        "name": team_ref["name"],
        "type": classification["type"],
        "age_category": classification["age_category"],
        "parent_team": infer_parent_team(team_ref["name"]),
        "confidence": "high",
        "url": team_ref["url"],
        "description": "",
        "image": "",
        "players": sort_entities(players),
    }


def main() -> None:
    personnages = load_json_list(PERSONNAGES_JSON)
    personnages_by_slug, name_to_slug = build_character_indexes(personnages)

    team_titles = discover_team_titles()
    print(f"[info] discovered {len(team_titles)} team pages from categories")

    team_to_player_slugs: dict[str, list[str]] = {}

    for team_title in team_titles:
        player_slugs = extract_players_from_team_page(team_title, name_to_slug)
        if not player_slugs:
            continue
        team_to_player_slugs[team_title] = player_slugs

    print(f"[info] team pages with extracted players: {len(team_to_player_slugs)}")

    equipes_payload: list[dict[str, Any]] = []
    player_to_team_refs: dict[str, list[dict[str, str]]] = {slug: [] for slug in personnages_by_slug}

    for team_title, player_slugs in team_to_player_slugs.items():
        payload = build_team_payload(team_title, player_slugs, personnages_by_slug)
        if not payload:
            continue

        equipes_payload.append(payload)

        team_ref = {
            "slug": payload["slug"],
            "name": payload["name"],
            "url": payload["url"],
            "confidence": "high",
        }

        for slug in player_slugs:
            if slug not in player_to_team_refs:
                continue
            if team_ref not in player_to_team_refs[slug]:
                player_to_team_refs[slug].append(team_ref)

    # Rebuild character teams from validated team rosters only
    for record in personnages:
        slug = str(record.get("slug", "")).strip()
        if not slug:
            continue
        record["teams"] = sort_entities(player_to_team_refs.get(slug, []))

    equipes_payload = sort_entities(equipes_payload)
    personnages_sorted = sorted(
        personnages,
        key=lambda entry: (
            int(entry.get("popularity", 999)),
            str(entry.get("name", "")).lower(),
        ),
    )

    safe_write_non_empty_list(
        EQUIPES_JSON,
        equipes_payload,
        minimum_items=0,
        label="equipes.json",
    )

    safe_write_non_empty_list(
        PERSONNAGES_JSON,
        personnages_sorted,
        minimum_items=50,
        label="personnages.json",
    )

    print(f"[ok] wrote {len(equipes_payload)} validated teams")
    print(f"[ok] updated {len(personnages_sorted)} characters from team rosters")


if __name__ == "__main__":
    main()
