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

TEAM_STRUCTURE_STOPWORDS = {
    "team",
    "teams",
    "level",
    "current career",
    "past career",
    "youth",
    "high school",
    "middle school",
    "elementary school",
    "club",
    "olympic",
}

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

def _is_structural_false_positive(candidate: str) -> bool:
    lowered = candidate.strip().lower()
    return lowered in TEAM_STRUCTURE_STOPWORDS

def _dedupe_normalized(candidates: list[str]) -> list[str]:
    teams: list[str] = []
    for candidate in candidates:
        normalized = normalize_entity_name(candidate)
        if not normalized or _is_structural_false_positive(normalized):
            continue
        if normalized not in teams:
            teams.append(normalized)
    return teams

def extract_teams_from_page_section_html(section_html: str) -> list[str]:
    if not section_html:
        return []

    linked_titles = re.findall(r'<a[^>]+title="([^"]+)"[^>]*>', section_html, flags=re.IGNORECASE)
    teams = _dedupe_normalized(linked_titles)
    if teams:
        return teams

    stripped = re.sub(r"<[^>]+>", " ", section_html)
    return _dedupe_normalized(split_list_field(stripped))

def extract_teams_from_section_links(section_links: list[str]) -> list[str]:
    return _dedupe_normalized(section_links)

def find_team_section_indexes(sections: list[dict[str, str]]) -> list[int]:
    indexes: list[int] = []
    for section in sections:
        line = normalize_entity_name(str(section.get("line", "")))
        if line.lower() != "team":
            continue

        raw_index = str(section.get("index", "")).strip()
        if not raw_index.isdigit():
            continue

        index = int(raw_index)
        if index not in indexes:
            indexes.append(index)
    return indexes
