#!/usr/bin/env python3
"""Enrich character data with teams and techniques from Captain Tsubasa Fandom.

This script is intentionally independent from sync_personnages.py:
- reads existing assets/data/personnages.json
- enriches each character with linked teams + techniques
- writes assets/data/equipes.json and assets/data/techniques.json
- rewrites personnages.json only when generation looks valid
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fandom.client import fetch_category_titles, fetch_intro_extract, fetch_page_html, fetch_page_wikitext
from fandom.extract_teams import extract_teams_from_infobox, extract_teams_from_page_html
from fandom.extract_techniques import (
    build_technique_to_users_map,
    extract_techniques_from_infobox,
    fetch_technique_titles_from_categories,
)
from fandom.normalize import extract_infobox_fields, normalize_entity_name, slugify
from fandom.relations import character_ref, entity_ref, sort_entities
from fandom.writers import safe_write_non_empty_list

PERSONNAGES_JSON = Path("assets/data/personnages.json")
EQUIPES_JSON = Path("assets/data/equipes.json")
TECHNIQUES_JSON = Path("assets/data/techniques.json")


def load_personnages() -> list[dict[str, Any]]:
    with PERSONNAGES_JSON.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise RuntimeError("assets/data/personnages.json must contain a list")
    return [entry for entry in payload if isinstance(entry, dict)]


def dedupe_refs(refs: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[str, dict[str, str]] = {}
    for ref in refs:
        slug = ref.get("slug", "").strip()
        if not slug:
            continue
        unique[slug] = ref
    return sort_entities(list(unique.values()))


def main() -> None:
    personnages = load_personnages()
    if not personnages:
        raise RuntimeError("No characters available for enrichment")

    category_titles = fetch_category_titles("Category:Characters")
    title_by_slug = {slugify(title.split("/", 1)[0].strip()): title.split("/", 1)[0].strip() for title in category_titles}

    known_character_titles = set(title_by_slug.values())
    team_links_by_character: dict[str, list[str]] = {}
    technique_links_by_character: dict[str, list[str]] = {}

    characters_with_teams = 0
    characters_with_techniques = 0

    print(f"[info] loaded {len(personnages)} characters from personnages.json")
    print(f"[info] found {len(title_by_slug)} character titles in Fandom category")

    for record in personnages:
        slug = str(record.get("slug", "")).strip()
        if not slug:
            continue
        title = title_by_slug.get(slug)
        if not title:
            continue

        try:
            wikitext = fetch_page_wikitext(title)
        except RuntimeError as exc:
            print(f"[warn] skip infobox fetch for {slug}: {exc}")
            continue

        infobox = extract_infobox_fields(wikitext)

        teams = extract_teams_from_infobox(infobox)
        if not teams:
            try:
                page_html = fetch_page_html(title)
            except RuntimeError as exc:
                print(f"[warn] skip team html fallback for {slug}: {exc}")
            else:
                teams = extract_teams_from_page_html(page_html)

        if teams:
            team_links_by_character[slug] = teams

        techniques = extract_techniques_from_infobox(infobox)
        if techniques:
            technique_links_by_character[slug] = techniques

    print(f"[info] team links from infobox/html: {sum(len(v) for v in team_links_by_character.values())}")
    print(f"[info] technique links from infobox: {sum(len(v) for v in technique_links_by_character.values())}")

    # Robust source priority for techniques:
    # 1) structured infobox fields (already collected)
    # 2) dedicated technique categories + page links to known characters
    technique_titles = fetch_technique_titles_from_categories()
    print(f"[info] technique titles discovered via categories: {len(technique_titles)}")

    technique_to_users = build_technique_to_users_map(technique_titles, known_character_titles)

    for technique_title, user_titles in technique_to_users.items():
        technique_name = normalize_entity_name(technique_title)
        if not technique_name or not user_titles:
            continue

        for user_title in user_titles:
            user_slug = slugify(user_title)
            technique_links_by_character.setdefault(user_slug, [])
            if technique_name not in technique_links_by_character[user_slug]:
                technique_links_by_character[user_slug].append(technique_name)

    characters_with_teams = sum(1 for links in team_links_by_character.values() if links)
    characters_with_techniques = sum(1 for links in technique_links_by_character.values() if links)
    print(f"[info] characters with teams extracted: {characters_with_teams}")
    print(f"[info] characters with techniques extracted: {characters_with_techniques}")

    teams_payload: dict[str, dict[str, Any]] = {}
    techniques_payload: dict[str, dict[str, Any]] = {}

    for record in personnages:
        slug = str(record.get("slug", "")).strip()
        if not slug:
            continue

        linked_team_refs = [entity_ref(team, "equipe") for team in team_links_by_character.get(slug, [])]
        linked_technique_refs = [entity_ref(technique, "technique") for technique in technique_links_by_character.get(slug, [])]

        record["teams"] = dedupe_refs(linked_team_refs)
        record["techniques"] = dedupe_refs(linked_technique_refs)

        character_pointer = character_ref(record)

        for team_ref in record["teams"]:
            team_slug = team_ref["slug"]
            if team_slug not in teams_payload:
                teams_payload[team_slug] = {
                    "slug": team_ref["slug"],
                    "name": team_ref["name"],
                    "url": team_ref["url"],
                    "description": "",
                    "image": "",
                    "players": [],
                }
            teams_payload[team_slug]["players"].append(character_pointer)

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

    # Optional descriptions for techniques, best effort.
    for technique in techniques:
        try:
            technique["description"] = fetch_intro_extract(technique["name"])
        except RuntimeError:
            technique["description"] = ""

    personnages_sorted = sorted(
        personnages,
        key=lambda entry: (int(entry.get("popularity", 999)), str(entry.get("name", "")).lower()),
    )

    safe_write_non_empty_list(EQUIPES_JSON, equipes, minimum_items=1, label="equipes.json")
    safe_write_non_empty_list(TECHNIQUES_JSON, techniques, minimum_items=1, label="techniques.json")
    safe_write_non_empty_list(PERSONNAGES_JSON, personnages_sorted, minimum_items=50, label="personnages.json")

    print(f"[info] total generated teams: {len(equipes)}")
    print(f"[info] total generated techniques: {len(techniques)}")
    print(f"[ok] wrote {len(equipes)} teams to {EQUIPES_JSON}")
    print(f"[ok] wrote {len(techniques)} techniques to {TECHNIQUES_JSON}")
    print(f"[ok] updated {len(personnages_sorted)} characters in {PERSONNAGES_JSON}")


if __name__ == "__main__":
    main()
