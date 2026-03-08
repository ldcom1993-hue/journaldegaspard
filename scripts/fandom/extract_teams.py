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

PAGE_LINK_BLACKLIST = {
    "Captain Tsubasa",
    "Description",
    "Biography",
    "History",
    "Trivia",
    "Notes",
    "External links",
    "Gallery",
    "Etymology",
    "Techniques",
    "List of techniques",
    "Manga",
    "Anime",
    "Movie",
    "OVA",
    "Episode",
    "Road to 2002",
    "Golden-23",
    "Rising Sun",
    "World Youth",
    "J Boys' Challenge",
    "Kids' Dream",
    "Battle of World Youth",
    "Overseas Fierce Fights",
}

POSITIVE_TEAM_PATTERNS = (
    "fc",
    "sc",
    "academy",
    "youth",
    "jr. youth",
    "junior youth",
    "hs",
    "ms",
    "elementary",
    "school",
    "national team",
    "olympic",
    "club",
    "united",
    "city",
    "sv",
    "ac",
    "inter",
    "borussia",
    "bayern",
    "juventus",
    "barcelona",
    "madrid",
    "flamengo",
    "santos",
    "river",
    "boca",
)

TEAM_FALSE_POSITIVE_PATTERNS = (
    "arc",
    "episode",
    "chapter",
    "manga",
    "anime",
    "movie",
    "ova",
    "soundtrack",
    "opening",
    "ending",
    "navigation",
    "template",
    "category",
    "list of",
    "technique",
    "dribble",
    "shot",
    "pass",
)

PAGE_LINK_BLACKLIST_LOWER = {item.lower() for item in PAGE_LINK_BLACKLIST}


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


def _contains_positive_team_pattern(candidate: str) -> bool:
    lowered = candidate.lower()
    candidate_words = set(re.findall(r"[a-z]+", lowered))
    for pattern in POSITIVE_TEAM_PATTERNS:
        if " " in pattern:
            if pattern in lowered:
                return True
            continue
        if pattern in candidate_words:
            return True
    return False


def _is_false_positive_link(candidate: str) -> bool:
    lowered = candidate.lower()
    if lowered in PAGE_LINK_BLACKLIST_LOWER:
        return True
    return any(pattern in lowered for pattern in TEAM_FALSE_POSITIVE_PATTERNS)


def extract_team_candidates_from_page_links(page_links: list[str], known_character_titles: set[str]) -> list[str]:
    candidates: list[str] = []
    known_character_titles_lower = {title.lower() for title in known_character_titles}

    for link in page_links:
        normalized = normalize_entity_name(link)
        if not normalized:
            continue

        lowered = normalized.lower()
        if lowered in known_character_titles_lower:
            continue
        if lowered.startswith(("category:", "template:", "file:")):
            continue
        if _is_structural_false_positive(normalized) or _is_false_positive_link(normalized):
            continue

        if _contains_positive_team_pattern(normalized):
            candidates.append(normalized)

    return candidates


def extract_teams_from_page_links(page_links: list[str], known_character_titles: set[str]) -> list[str]:
    candidates = extract_team_candidates_from_page_links(page_links, known_character_titles)
    return _dedupe_normalized(candidates)

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
