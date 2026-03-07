from __future__ import annotations

import html
import re
import unicodedata


COMPETITION_KEYWORDS = (
    "tournament",
    "championship",
    "cup",
    "league",
    "qualifier",
)

NATIONAL_TEAM_KEYWORDS = (
    "national team",
    "all japan",
)

CLUB_TEAM_KEYWORDS = (
    " fc",
    "fc ",
    " sc",
    "sc ",
    " club",
    "sv ",
    "ac ",
    "inter ",
    "juventus",
    "barcelona",
    "madrid",
    "flamengo",
    "bayern",
    "hamburger",
    "iwata",
    "antlers",
)


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9\s-]", "", ascii_text.lower())
    slug = re.sub(r"\s+", "-", slug).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or "entity"


def normalize_infobox_value(value: str) -> str:
    value = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)
    value = re.sub(r"<ref[^>]*>.*?</ref>", "", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\{\{(?:lang\|ja\|)?([^{}|]+(?:\|[^{}|]+)*)\}\}", lambda m: m.group(1).split("|")[-1], value)
    value = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", value)
    value = re.sub(r"\[https?://[^\s\]]+\s*([^\]]*)\]", r"\1", value)
    value = re.sub(r"''+", "", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" |")


def clean_text(value: str) -> str:
    text = normalize_infobox_value(str(value or ""))
    text = re.sub(r"\s*\(\s*\)", "", text)
    text = re.sub(r"\s*[,;]\s*$", "", text)
    return text.strip()


def split_list_field(value: str) -> list[str]:
    cleaned = clean_text(value)
    if not cleaned:
        return []

    pieces = re.split(r"(?:\n|,|;|/|\|)", cleaned)
    items: list[str] = []

    for piece in pieces:
        entry = piece.strip(" -*•")
        if not entry:
            continue
        if entry not in items:
            items.append(entry)

    return items


def extract_template_block(wikitext: str) -> str:
    for template_start in re.finditer(r"\{\{\s*([^\n\|\}]+)", wikitext):
        template_name = template_start.group(1).strip().lower()

        if "infobox" not in template_name and "character" not in template_name:
            continue

        start = template_start.start()
        i = start
        depth = 0

        while i < len(wikitext) - 1:
            pair = wikitext[i : i + 2]

            if pair == "{{":
                depth += 1
                i += 2
                continue

            if pair == "}}":
                depth -= 1
                i += 2

                if depth <= 0:
                    return wikitext[start:i]

                continue

            i += 1

        return ""

    return ""


def extract_infobox_fields(wikitext: str) -> dict[str, str]:
    infobox_text = extract_template_block(wikitext)

    if not infobox_text:
        return {}

    values: dict[str, str] = {}
    current_key: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current_key, buffer

        if current_key is None:
            return

        joined = normalize_infobox_value("\n".join(buffer))
        values[current_key] = joined
        current_key = None
        buffer = []

    for raw_line in infobox_text.splitlines():
        line = raw_line.rstrip()

        key_match = re.match(r"^\|\s*([a-zA-Z0-9_]+)\s*=\s*(.*)$", line)

        if key_match:
            flush()
            current_key = key_match.group(1).lower()
            buffer = [key_match.group(2)]
            continue

        if current_key is not None:
            buffer.append(line)

    flush()
    return values


def normalize_entity_name(value: str) -> str:
    name = clean_text(value)
    return re.sub(r"\s+", " ", name).strip()


def _contains_any_keyword(lowered_name: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in lowered_name for keyword in keywords)


def classify_team(name: str) -> dict[str, str]:
    normalized_name = normalize_entity_name(name)
    lowered_name = normalized_name.lower()

    if _contains_any_keyword(lowered_name, COMPETITION_KEYWORDS):
        return {"type": "competition", "age_category": "adult"}

    if "elementary school" in lowered_name or lowered_name.endswith(" es"):
        return {"type": "school", "age_category": "elementary"}

    if (
        "middle school" in lowered_name
        or "junior high" in lowered_name
        or lowered_name.endswith(" ms")
    ):
        return {"type": "school", "age_category": "middle-school"}

    if "high school" in lowered_name or lowered_name.endswith(" hs"):
        return {"type": "school", "age_category": "high-school"}

    if "olympic" in lowered_name:
        return {"type": "national", "age_category": "olympic"}

    if "junior youth" in lowered_name or "youth" in lowered_name:
        if _contains_any_keyword(lowered_name, CLUB_TEAM_KEYWORDS):
            return {"type": "club", "age_category": "youth"}

        return {"type": "national", "age_category": "youth"}

    club_youth_markers = ("jr", "jr.", "academy", "u-", "youth squad")

    if _contains_any_keyword(lowered_name, club_youth_markers):
        return {"type": "club", "age_category": "youth"}

    if _contains_any_keyword(lowered_name, CLUB_TEAM_KEYWORDS):
        return {"type": "club", "age_category": "adult"}

    if "all japan" in lowered_name:
        return {"type": "national", "age_category": "youth"}

    if _contains_any_keyword(lowered_name, NATIONAL_TEAM_KEYWORDS):
        return {"type": "national", "age_category": "adult"}

    return {"type": "club", "age_category": "adult"}


def infer_parent_team(name: str) -> str | None:
    """Infer base team family name for school/club/national variants."""
    normalized_name = normalize_entity_name(name)

    if not normalized_name:
        return None

    parent = re.sub(
        r"\s+(elementary school|middle school|high school|junior high|ms|hs|es|sc|fc|jr\.? youth|youth|national team)$",
        "",
        normalized_name,
        flags=re.IGNORECASE,
    ).strip()

    if not parent or parent.casefold() == normalized_name.casefold():
        return None

    return parent
