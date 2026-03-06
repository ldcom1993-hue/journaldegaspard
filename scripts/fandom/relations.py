from __future__ import annotations

from typing import Any

from .normalize import normalize_entity_name, slugify

BASE_PATH = "/univers/olive-et-tom"


def character_ref(record: dict[str, Any]) -> dict[str, str]:
    slug = str(record.get("slug", "")).strip()
    name = str(record.get("name", "")).strip() or slug
    return {
        "slug": slug,
        "name": name,
        "url": f"{BASE_PATH}/personnage.html?slug={slug}",
    }


def entity_ref(name: str, kind: str) -> dict[str, str]:
    normalized_name = normalize_entity_name(name)
    slug = slugify(normalized_name)
    return {
        "slug": slug,
        "name": normalized_name,
        "url": f"{BASE_PATH}/{kind}.html?slug={slug}",
    }


def sort_entities(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: (str(item.get("name", "")).lower(), str(item.get("slug", "")).lower()))
