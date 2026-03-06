from __future__ import annotations

import re

from .normalize import normalize_entity_name, split_list_field

TEAM_INFOBOX_FIELDS = (
    "team",
    "former_team",
    "club",
    "current_team",
    "national_team",
    "youth_team",
    "team_name",
)


def extract_teams_from_infobox(infobox: dict[str, str]) -> list[str]:
    teams: list[str] = []
    for field in TEAM_INFOBOX_FIELDS:
        raw_value = infobox.get(field, "")
        for candidate in split_list_field(raw_value):
            normalized = normalize_entity_name(candidate)
            if not normalized:
                continue
            if normalized not in teams:
                teams.append(normalized)
    return teams


def extract_teams_from_page_html(page_html: str) -> list[str]:
    if not page_html:
        return []

    teams: list[str] = []

    section_match = re.search(
        r'<h[2-6][^>]*>\s*<span[^>]*>\s*Team\s*</span>\s*</h[2-6]>(.*?)(?=<h[2-6][^>]*>|$)',
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not section_match:
        return []

    section_html = section_match.group(1)

    for linked_team in re.findall(r'<a[^>]+title="([^"]+)"[^>]*>', section_html, flags=re.IGNORECASE):
        normalized = normalize_entity_name(linked_team)
        if not normalized:
            continue
        if normalized.lower() in {"team", "teams"}:
            continue
        if normalized not in teams:
            teams.append(normalized)

    if teams:
        return teams

    stripped = re.sub(r"<[^>]+>", " ", section_html)
    for candidate in split_list_field(stripped):
        normalized = normalize_entity_name(candidate)
        if not normalized:
            continue
        if normalized.lower() in {"team", "teams"}:
            continue
        if normalized not in teams:
            teams.append(normalized)

    return teams
