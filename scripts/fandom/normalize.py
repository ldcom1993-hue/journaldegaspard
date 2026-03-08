from __future__ import annotations

import re
import unicodedata
import html


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9\s-]", "", ascii_text.lower())
    slug = re.sub(r"\s+", "-", slug).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or "entity"


def normalize_infobox_value(value: str) -> str:
    value = re.sub(r"<ref[^>]*>.*?</ref>", "", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" |")


def normalize_entity_name(value: str) -> str:
    if not value:
        return ""

    name = normalize_infobox_value(str(value))
    name = re.sub(r"\s+", " ", name).strip()

    return name


def extract_infobox_fields(wikitext: str) -> dict[str, str]:
    values: dict[str, str] = {}

    for line in wikitext.splitlines():
        if "=" not in line:
            continue

        if line.strip().startswith("|"):

            parts = line.split("=", 1)

            key = parts[0].strip("| ").lower()
            value = parts[1].strip()

            values[key] = normalize_infobox_value(value)

    return values


def classify_team(name: str) -> dict[str, str]:

    lowered = name.lower()

    if "elementary school" in lowered:
        return {"type": "school", "age_category": "elementary"}

    if "middle school" in lowered:
        return {"type": "school", "age_category": "middle-school"}

    if "high school" in lowered:
        return {"type": "school", "age_category": "high-school"}

    if "jr" in lowered or "youth" in lowered:
        return {"type": "national", "age_category": "youth"}

    if "olympic" in lowered:
        return {"type": "national", "age_category": "olympic"}

    if "fc" in lowered or "sc" in lowered or "sv" in lowered:
        return {"type": "club", "age_category": "adult"}

    return {"type": "club", "age_category": "adult"}


def infer_parent_team(name: str) -> str | None:

    n = normalize_entity_name(name)

    replacements = [
        " Elementary School",
        " Middle School",
        " High School",
        " Jr. Youth",
        " Youth",
        " SC",
        " FC",
    ]

    for r in replacements:
        if n.endswith(r):
            return n.replace(r, "").strip()

    if "All Japan" in n or "Olympic Japan" in n:
        return "Japan"

    return None
