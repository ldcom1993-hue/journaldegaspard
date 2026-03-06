from __future__ import annotations

import html
import re
import unicodedata


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
