from __future__ import annotations

import re

from .client import fetch_category_titles, fetch_page_links
from .normalize import clean_text, normalize_entity_name, split_list_field

TECHNIQUE_INFOBOX_FIELDS = (
    "technique",
    "techniques",
    "special_technique",
    "special_move",
    "special_moves",
    "move",
    "moves",
    "shot",
    "skills",
)

TECHNIQUE_CATEGORY_CANDIDATES = (
    "Category:Special Techniques",
    "Category:Special_Techniques",
    "Category:Techniques",
    "Category:Moves",
)


def extract_techniques_from_infobox(infobox: dict[str, str]) -> list[str]:
    techniques: list[str] = []
    for field in TECHNIQUE_INFOBOX_FIELDS:
        for candidate in split_list_field(infobox.get(field, "")):
            normalized = normalize_entity_name(candidate)
            if normalized and normalized not in techniques:
                techniques.append(normalized)
    return techniques


def _is_probable_technique_name(title: str) -> bool:
    normalized = clean_text(title)
    if not normalized:
        return False
    if ":" in normalized:
        return False
    if normalized.lower() in {"special techniques", "techniques", "moves"}:
        return False
    return bool(re.search(r"[A-Za-z]", normalized))


def fetch_technique_titles_from_categories() -> list[str]:
    titles: list[str] = []
    for category in TECHNIQUE_CATEGORY_CANDIDATES:
        try:
            candidates = fetch_category_titles(category)
        except RuntimeError:
            continue

        for title in candidates:
            if not _is_probable_technique_name(title):
                continue
            if title not in titles:
                titles.append(title)

    return titles


def build_technique_to_users_map(technique_titles: list[str], known_character_titles: set[str]) -> dict[str, list[str]]:
    technique_to_users: dict[str, list[str]] = {}
    for title in technique_titles:
        try:
            links = fetch_page_links(title)
        except RuntimeError:
            continue

        users: list[str] = []
        for linked_title in links:
            if linked_title in known_character_titles and linked_title not in users:
                users.append(linked_title)

        technique_to_users[title] = users

    return technique_to_users
