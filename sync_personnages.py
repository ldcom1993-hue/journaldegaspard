#!/usr/bin/env python3
"""Synchronize Captain Tsubasa characters data from Fandom Category:Characters.

Behavior:
- Fetches category titles with pagination
- Normalizes subpages (e.g. "Pierre Le Cid/Techniques" -> "Pierre Le Cid")
- Excludes only obvious non-character namespaces
- Non-destructive merge with existing assets/data/personnages.json
- Adds missing characters, fills missing fields, downloads missing images
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


OPENER = build_opener(ProxyHandler({}))
OPENER.addheaders = [("User-Agent", "journaldegaspard-sync/2.0")]


def slugify(text: str) -> str:
    """Create lowercase URL-safe slug with hyphens."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9\s-]", "", ascii_text.lower())
    slug = re.sub(r"\s+", "-", slug).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or "character"


def should_exclude_title(title: str) -> bool:
    excluded_prefixes = ("Category:", "Template:", "File:")
    return title.startswith(excluded_prefixes)


def get_base_title(title: str) -> str:
    return title.split("/", 1)[0].strip()


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def web_path_to_local(path: str | None) -> Path | None:
    if not path:
        return None
    if not path.startswith("/"):
        return Path(path)
    return Path(path[1:])


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
    raw_titles: list[str] = []
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
        raw_titles.extend(member["title"] for member in members if "title" in member)

        continuation = payload.get("continue")
        if not continuation:
            break
        params.update(continuation)

    normalized_titles: list[str] = []
    seen_bases: set[str] = set()

    for title in raw_titles:
        base_title = get_base_title(title)
        if not base_title or should_exclude_title(base_title):
            continue
        if base_title in seen_bases:
            continue
        seen_bases.add(base_title)
        normalized_titles.append(base_title)

    return normalized_titles


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


def load_existing_records() -> list[dict[str, Any]]:
    if not OUTPUT_JSON.exists():
        return []

    with OUTPUT_JSON.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        return []

    return [record for record in payload if isinstance(record, dict)]


def merge_missing_fields(existing: dict[str, Any], incoming: dict[str, Any]) -> bool:
    changed = False

    for key in ("name", "japaneseName", "position", "nationality", "description", "image"):
        if is_empty(existing.get(key)) and not is_empty(incoming.get(key)):
            existing[key] = incoming[key]
            changed = True

    if is_empty(existing.get("teams")) and not is_empty(incoming.get("teams")):
        existing["teams"] = incoming["teams"]
        changed = True

    existing_infobox = existing.get("infobox")
    if not isinstance(existing_infobox, dict):
        existing_infobox = {}
        existing["infobox"] = existing_infobox

    incoming_infobox = incoming.get("infobox", {})
    if isinstance(incoming_infobox, dict):
        for field in INFOBOX_FIELDS:
            if is_empty(existing_infobox.get(field)) and not is_empty(incoming_infobox.get(field)):
                existing_infobox[field] = incoming_infobox[field]
                changed = True

    return changed


def needs_refresh(existing: dict[str, Any]) -> bool:
    keys_to_check = ("name", "japaneseName", "position", "nationality", "description", "image", "teams", "infobox")
    if any(is_empty(existing.get(key)) for key in keys_to_check):
        return True

    local_image = web_path_to_local(existing.get("image"))
    return bool(local_image and not local_image.exists())


def main() -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    existing_records = load_existing_records()
    records_by_slug: dict[str, dict[str, Any]] = {}

    for record in existing_records:
        slug = record.get("slug")
        if not isinstance(slug, str) or not slug:
            continue
        records_by_slug[slug] = record

    titles = fetch_category_titles()

    print(f"Fetched {len(titles)} unique base titles from category")
    print(f"Loaded {len(records_by_slug)} existing records")

    for index, title in enumerate(titles, start=1):
        print(f"[{index}/{len(titles)}] {title}")
        slug = slugify(title)

        existing = records_by_slug.get(slug)
        if existing and not needs_refresh(existing):
            print(f"[skipped-existing] {title}")
            continue

        wikitext = fetch_page_wikitext(title)
        infobox = extract_infobox_fields(wikitext)
        description = fetch_intro_extract(title)
        image_url = fetch_original_image_url(title)
        image_path = download_image_if_needed(slug, image_url)

        incoming = build_record(title, infobox, description, image_path)

        if existing:
            updated = merge_missing_fields(existing, incoming)
            local_image = web_path_to_local(existing.get("image"))
            if local_image and not local_image.exists() and image_path:
                existing["image"] = existing.get("image") or image_path
                updated = True

            if updated:
                print(f"[updated] {title}")
            else:
                print(f"[skipped-existing] {title}")
            continue

        records_by_slug[slug] = incoming
        print(f"[added] {title}")

    records = list(records_by_slug.values())
    records.sort(key=lambda item: str(item.get("name", item.get("slug", ""))).casefold())

    with OUTPUT_JSON.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Wrote {len(records)} records to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
