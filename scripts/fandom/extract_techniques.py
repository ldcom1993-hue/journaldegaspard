from __future__ import annotations

import re

from .client import fetch_category_titles, fetch_page_links
from .normalize import clean_text, normalize_entity_name, split_list_field, slugify

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
    "Category:List of techniques",
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
    if normalized.lower() in {"special techniques", "techniques", "moves", "list of techniques"}:
        return False
    return bool(re.search(r"[A-Za-z]", normalized))


def _character_title_from_techniques_page(title: str) -> str | None:
    cleaned = clean_text(title)
    if not cleaned:
        return None

    if not cleaned.endswith("/Techniques"):
        return None

    character_title = cleaned[: -len("/Techniques")].strip()
    return character_title or None


def _is_probable_technique_link(title: str, owner_title: str) -> bool:
    normalized = clean_text(title)
    if not normalized:
        return False
    if normalized == owner_title:
        return False
    if normalized.startswith(("Category:", "Template:", "File:")):
        return False
    lowered = normalized.lower()
    if lowered.endswith("/techniques"):
        return False
    if lowered in {
        "techniques",
        "special techniques",
        "category:list of techniques",
        "list of techniques",
        "team",
    }:
        return False
    return _is_probable_technique_name(normalized)


def fetch_technique_titles_from_categories() -> list[str]:
    titles: list[str] = []
    for category in TECHNIQUE_CATEGORY_CANDIDATES:
        try:
            candidates = fetch_category_titles(category)
        except RuntimeError:
            continue

        for title in candidates:
            if title not in titles:
                titles.append(title)

    return titles


def build_technique_to_users_map(technique_titles: list[str], known_character_titles: set[str]) -> dict[str, list[str]]:
    technique_to_users: dict[str, list[str]] = {}
    known_character_slugs = {slugify(title): title for title in known_character_titles}

    for title in technique_titles:
        character_title = _character_title_from_techniques_page(title)
        if not character_title:
            continue

        character_slug = slugify(character_title)
        canonical_character_title = known_character_slugs.get(character_slug)
        if not canonical_character_title:
            continue

        try:
            links = fetch_page_links(title)
        except RuntimeError:
            continue

        for linked_title in links:
            if not _is_probable_technique_link(linked_title, canonical_character_title):
                continue
            technique_to_users.setdefault(linked_title, [])
            if canonical_character_title not in technique_to_users[linked_title]:
                technique_to_users[linked_title].append(canonical_character_title)

    return technique_to_users
