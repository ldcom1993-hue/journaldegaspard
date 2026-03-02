#!/usr/bin/env python3
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

JS_PATH = Path("assets/js/personnages.js")
IMAGES_DIR = Path("assets/images/olive-et-tom")
FANDOM_API = "https://captaintsubasa.fandom.com/api.php"
IMAGE_EXTENSIONS = ("png", "jpg", "jpeg", "webp")
SLUG_LINK_RE = re.compile(r'^/univers/olive-et-tom/personnages/([a-z0-9-]+)\.html$')

# Known aliases where French-localized slug differs from canonical wiki title.
TITLE_OVERRIDES = {
    "olivier-atton": "Tsubasa_Ozora",
    "ben-becker": "Taro_Misaki",
}


def fetch_json(url: str) -> Optional[dict]:
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def score_title(title: str, slug: str) -> int:
    slug_tokens = slug.lower().split("-")
    title_tokens = re.split(r"[_\s]+", title.lower())
    overlap = len(set(slug_tokens) & set(title_tokens))
    starts = int(title.lower().startswith(slug_tokens[0])) if slug_tokens else 0
    exact = int(title.lower().replace("_", "-") == slug.lower())
    return exact * 10 + overlap * 3 + starts


def resolve_title(slug: str) -> Optional[str]:
    if slug in TITLE_OVERRIDES:
        return TITLE_OVERRIDES[slug]

    query = urllib.parse.urlencode(
        {
            "action": "query",
            "list": "search",
            "srsearch": slug,
            "format": "json",
        }
    )
    data = fetch_json(f"{FANDOM_API}?{query}")
    if not data:
        return None

    results = data.get("query", {}).get("search", [])
    if not results:
        return None

    ranked = sorted(
        (item.get("title", "") for item in results if item.get("title")),
        key=lambda t: score_title(t, slug),
        reverse=True,
    )
    return ranked[0] if ranked else None


def clean_html_text(value: str) -> str:
    value = re.sub(r"<br\s*/?>", ", ", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    value = value.replace("&nbsp;", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip(" :\n\t")


def extract_infobox_value(html: str, label: str) -> Optional[str]:
    pattern = re.compile(
        rf"<[^>]*data-source=[\"']?{re.escape(label)}[\"']?[^>]*>(.*?)</(?:div|section|tr)>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(html)
    if not match:
        return None

    block = match.group(1)
    val_match = re.search(
        r"<[^>]*class=[\"'][^\"']*(?:pi-data-value|infobox-data)[^\"']*[\"'][^>]*>(.*?)</[^>]+>",
        block,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not val_match:
        return None

    cleaned = clean_html_text(val_match.group(1))
    return cleaned or None


def extract_description(html: str) -> Optional[str]:
    for paragraph in re.findall(r"<p>(.*?)</p>", html, flags=re.IGNORECASE | re.DOTALL):
        cleaned = clean_html_text(paragraph)
        if cleaned and len(cleaned) > 40:
            return cleaned
    return None


def fetch_fandom_data(slug: str) -> Dict[str, str]:
    title = resolve_title(slug)
    if not title:
        return {}

    query = urllib.parse.urlencode(
        {
            "action": "parse",
            "page": title,
            "prop": "text",
            "format": "json",
        }
    )
    data = fetch_json(f"{FANDOM_API}?{query}")
    if not data:
        return {}

    html = data.get("parse", {}).get("text", {}).get("*", "")
    if not html:
        return {}

    japanese_name = extract_infobox_value(html, "japanese") or extract_infobox_value(html, "kanji")
    romaji_name = extract_infobox_value(html, "romaji")
    team = extract_infobox_value(html, "team")
    former_teams = extract_infobox_value(html, "former_teams")
    role = extract_infobox_value(html, "role") or extract_infobox_value(html, "position")
    description = extract_description(html)

    merged_team = team
    if not merged_team and former_teams:
        merged_team = former_teams

    return {
        "japaneseName": japanese_name or romaji_name or "",
        "team": merged_team or "",
        "description": description or "",
        "role": role or "",
    }


def find_character_blocks(content: str) -> List[Tuple[int, int, str]]:
    array_match = re.search(r"const\s+characters\s*=\s*\[", content)
    if not array_match:
        return []

    start = array_match.end()
    depth = 0
    blocks = []
    block_start = None

    i = start
    while i < len(content):
        ch = content[i]
        if ch == "{":
            if depth == 0:
                block_start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and block_start is not None:
                end = i + 1
                blocks.append((block_start, end, content[block_start:end]))
                block_start = None
        elif ch == "]" and depth == 0:
            break
        i += 1
    return blocks


def get_field(block: str, field: str) -> Optional[str]:
    m = re.search(rf"{field}:\s*\"([^\"]*)\"", block)
    return m.group(1) if m else None


def set_field(block: str, field: str, value: str) -> Tuple[str, bool]:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    pattern = re.compile(rf"({field}:\s*)\"([^\"]*)\"")
    m = pattern.search(block)
    if not m:
        return block, False
    if m.group(2) == value:
        return block, False
    return pattern.sub(rf"\\1\"{escaped}\"", block, count=1), True


def find_local_image(slug: str) -> Optional[str]:
    for ext in IMAGE_EXTENSIONS:
        candidate = IMAGES_DIR / f"{slug}.{ext}"
        if candidate.exists():
            return f"/assets/images/olive-et-tom/{slug}.{ext}"
    return None


def main() -> int:
    if not JS_PATH.exists():
        print(f"File not found: {JS_PATH}", file=sys.stderr)
        return 1

    content = JS_PATH.read_text(encoding="utf-8")
    blocks = find_character_blocks(content)
    if not blocks:
        print("No character blocks found", file=sys.stderr)
        return 1

    rebuilt_parts = []
    cursor = 0
    total_changes = 0

    for start, end, block in blocks:
        rebuilt_parts.append(content[cursor:start])
        new_block = block

        link = get_field(block, "link") or ""
        slug_match = SLUG_LINK_RE.match(link)
        if not slug_match:
            rebuilt_parts.append(new_block)
            cursor = end
            continue

        slug = slug_match.group(1)
        updated_image = False
        updated_fandom = False

        image_path = find_local_image(slug)
        if image_path:
            new_block, changed = set_field(new_block, "image", image_path)
            if changed:
                updated_image = True
                total_changes += 1

        fandom = fetch_fandom_data(slug)
        for field in ("japaneseName", "team", "description"):
            incoming = fandom.get(field, "").strip()
            if not incoming:
                continue
            current = get_field(new_block, field)
            if current is None:
                continue
            if current.strip():
                continue
            new_block, changed = set_field(new_block, field, incoming)
            if changed:
                updated_fandom = True
                total_changes += 1

        if updated_image:
            print(f"Updated image for {slug}")
        if updated_fandom:
            print(f"Updated fandom data for {slug}")
        if not updated_image and not updated_fandom:
            print(f"Skipped {slug}")

        rebuilt_parts.append(new_block)
        cursor = end

    rebuilt_parts.append(content[cursor:])
    new_content = "".join(rebuilt_parts)

    if total_changes > 0 and new_content != content:
        JS_PATH.write_text(new_content, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
