#!/usr/bin/env python3
"""Rebuild Captain Tsubasa characters data from Fandom Category:Characters.

- Paginates categorymembers with `continue`
- Filters out non-character pages
- Extracts infobox fields from page wikitext
- Fetches intro extract (plaintext)
- Fetches original page image and downloads it locally
- Writes sorted JSON to assets/data/personnages.json
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

API_URL = "https://captaintsubasa.fandom.com/api.php"
CATEGORY_TITLE = "Category:Characters"
IMAGE_DIR = Path("assets/images/olive-et-tom")
OUTPUT_JSON = Path("assets/data/personnages.json")

EXCLUDED_SUBSTRINGS = (
    "Episode",
    "Technique",
    "Game",
    "Season",
    "Dream Team",
)

INFOBOX_FIELDS = [
    "name",
    "japanese",
    "romaji",
    "alias",
    "gender",
    "birthday",
    "age",
    "height",
    "weight",
    "blood",
    "position",
    "team",
    "former_team",
    "nationality",
    "status",
    "occupation",
]

TEMPLATE_PREFIXES = (
    "Character",
    "Infobox Character",
    "Infobox character",
    "Infobox manga character",
)


def slugify(text: str) -> str:
    """Create lowercase URL-safe slug with hyphens."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9\s-]", "", ascii_text.lower())
    slug = re.sub(r"\s+", "-", slug).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or "character"


def should_exclude_title(title: str) -> bool:
    if "/" in title:
        return True
    return any(token in title for token in EXCLUDED_SUBSTRINGS)


OPENER = build_opener(ProxyHandler({}))
OPENER.addheaders = [("User-Agent", "journaldegaspard-sync/2.0")]


def api_get_json(params: dict[str, Any]) -> dict[str, Any]:
    query = urlencode(params)
    request = Request(f"{API_URL}?{query}")
    try:
        with OPENER.open(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"API request failed: {exc}") from exc


def download_binary(url: str) -> bytes:
    request = Request(url)
    try:
        with OPENER.open(request, timeout=60) as response:
            return response.read()
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"Download failed: {exc}") from exc


def fetch_category_titles() -> list[str]:
    titles: list[str] = []
    params: dict[str, Any] = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": CATEGORY_TITLE,
        "cmlimit": "500",
        "format": "json",
    }

    while True:
        payload = api_get_json(params)

        members = payload.get("query", {}).get("categorymembers", [])
        titles.extend(member["title"] for member in members if "title" in member)

        continuation = payload.get("continue")
        if not continuation:
            break
        params.update(continuation)

    return titles


def extract_template_block(wikitext: str) -> str:
    """Return first likely character infobox template block."""
    for template_start in re.finditer(r"\{\{\s*([^\n\|\}]+)", wikitext):
        template_name = template_start.group(1).strip()
        if not template_name.startswith(TEMPLATE_PREFIXES):
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


def normalize_infobox_value(value: str) -> str:
    value = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)
    value = re.sub(r"<ref[^>]*>.*?</ref>", "", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\{\{(?:lang\|ja\|)?([^{}|]+(?:\|[^{}|]+)*)\}\}", lambda m: m.group(1).split("|")[-1], value)
    value = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", value)
    value = re.sub(r"\[https?://[^\s\]]+\s*([^\]]*)\]", r"\1", value)
    value = re.sub(r"''+", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" |")


def extract_infobox_fields(wikitext: str) -> dict[str, str]:
    infobox_text = extract_template_block(wikitext)
    values: dict[str, str] = {key: "" for key in INFOBOX_FIELDS}
    if not infobox_text:
        return values

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
            key = key_match.group(1).lower()
            if key in values:
                current_key = key
                buffer = [key_match.group(2)]
            continue

        if current_key is not None:
            buffer.append(line)

    flush()
    return values


def fetch_page_wikitext(title: str) -> str:
    params = {
        "action": "parse",
        "page": title,
        "prop": "wikitext",
        "format": "json",
    }
    payload = api_get_json(params)
    return payload.get("parse", {}).get("wikitext", {}).get("*", "")


def fetch_intro_extract(title: str) -> str:
    params = {
        "action": "query",
        "prop": "extracts",
        "titles": title,
        "exintro": "1",
        "plaintext": "1",
        "format": "json",
    }
    payload = api_get_json(params)
    pages = payload.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), {})
    text = page.get("extract", "") or ""
    return re.sub(r"\s+", " ", text).strip()


def fetch_original_image_url(title: str) -> str | None:
    params = {
        "action": "query",
        "prop": "pageimages",
        "titles": title,
        "piprop": "original",
        "format": "json",
    }
    payload = api_get_json(params)
    pages = payload.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), {})
    return page.get("original", {}).get("source")


def download_image_if_needed(slug: str, image_url: str | None) -> str:
    path = IMAGE_DIR / f"{slug}.png"
    web_path = f"/{path.as_posix()}"

    if path.exists():
        print(f"[skip-image] {slug}")
        return web_path

    if not image_url:
        print(f"[no-image] {slug}")
        return web_path

    content = download_binary(image_url)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    print(f"[downloaded] {slug}")
    return web_path


def parse_teams(infobox: dict[str, str]) -> list[str]:
    raw_parts = [infobox.get("team", ""), infobox.get("former_team", "")]
    teams: list[str] = []
    for part in raw_parts:
        if not part:
            continue
        pieces = [p.strip() for p in re.split(r"(?:<br\s*/?>|,|;|\n)", part) if p.strip()]
        for piece in pieces:
            if piece not in teams:
                teams.append(piece)
    return teams


def build_record(title: str, infobox: dict[str, str], description: str, image_path: str) -> dict[str, Any]:
    slug = slugify(title)
    display_name = infobox.get("name") or title
    return {
        "slug": slug,
        "name": display_name,
        "japaneseName": infobox.get("japanese", ""),
        "position": infobox.get("position", ""),
        "teams": parse_teams(infobox),
        "nationality": infobox.get("nationality", ""),
        "description": description,
        "image": image_path,
        "infobox": infobox,
    }


def main() -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    all_titles = fetch_category_titles()
    titles = [title for title in all_titles if not should_exclude_title(title)]

    print(f"Fetched {len(all_titles)} category titles")
    print(f"Kept {len(titles)} titles after filtering")

    records: list[dict[str, Any]] = []

    for index, title in enumerate(titles, start=1):
        print(f"[{index}/{len(titles)}] {title}")
        slug = slugify(title)

        wikitext = fetch_page_wikitext(title)
        infobox = extract_infobox_fields(wikitext)

        description = fetch_intro_extract(title)
        image_url = fetch_original_image_url(title)
        image_path = download_image_if_needed(slug, image_url)

        records.append(build_record(title, infobox, description, image_path))

    records.sort(key=lambda item: item["name"].casefold())

    with OUTPUT_JSON.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Wrote {len(records)} records to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
