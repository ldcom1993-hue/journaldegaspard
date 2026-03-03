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

import html
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

ARC_CODES = ("RT", "BWY", "JBC", "WY", "G23", "RS", "MS", "ES", "KD")

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
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\{\{(?:lang\|ja\|)?([^{}|]+(?:\|[^{}|]+)*)\}\}", lambda m: m.group(1).split("|")[-1], value)
    value = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", value)
    value = re.sub(r"\[https?://[^\s\]]+\s*([^\]]*)\]", r"\1", value)
    value = re.sub(r"''+", "", value)
    value = html.unescape(value)
    value = re.sub(r"\bClick\s*'?\s*Expand'?\s*(?:to\s*view)?\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" |")


def clean_text(value: str) -> str:
    text = normalize_infobox_value(value)
    text = re.sub(r"\s*\(\s*\)", "", text)
    text = re.sub(r"\s*[,;]\s*$", "", text)
    return text.strip()


def to_int(value: str) -> int | None:
    match = re.search(r"(\d+)", value)
    if not match:
        return None
    return int(match.group(1))


def parse_measurements_by_arc(raw_value: str, unit: str) -> dict[str, int]:
    cleaned = clean_text(raw_value)
    if not cleaned:
        return {}

    pairs = re.findall(rf"(\d+)\s*{unit}\s*(?:\(([^)]+)\))?", cleaned, flags=re.IGNORECASE)
    if not pairs:
        value = to_int(cleaned)
        return {"default": value} if value is not None else {}

    parsed: dict[str, int] = {}
    default_values: list[int] = []
    for value_text, arc_text in pairs:
        value = int(value_text)
        arcs = [arc.strip().upper() for arc in re.split(r"[/,&]", arc_text or "") if arc.strip()]
        normalized_arcs = [arc for arc in arcs if arc in ARC_CODES]

        if not normalized_arcs:
            default_values.append(value)
            continue

        for arc in normalized_arcs:
            parsed[arc] = value

    if parsed:
        return parsed
    if default_values:
        return {"default": default_values[0]}
    return {}


def parse_physical(infobox: dict[str, str]) -> dict[str, dict[str, int]]:
    heights = parse_measurements_by_arc(infobox.get("height", ""), "cm")
    weights = parse_measurements_by_arc(infobox.get("weight", ""), "kg")

    arc_keys = list(dict.fromkeys(list(heights.keys()) + list(weights.keys())))
    physical: dict[str, dict[str, int]] = {}
    for arc in arc_keys:
        arc_data: dict[str, int] = {}
        if arc in heights:
            arc_data["height_cm"] = heights[arc]
        if arc in weights:
            arc_data["weight_kg"] = weights[arc]
        if arc_data:
            physical[arc] = arc_data

    return physical


def split_name_fields(infobox: dict[str, str], title: str) -> dict[str, str]:
    latin_source = clean_text(infobox.get("romaji", "") or infobox.get("name", "") or title)
    japanese_source = clean_text(infobox.get("japanese", "") or infobox.get("name", ""))

    kanji_match = " ".join(re.findall(r"[\u3040-\u30ff\u3400-\u9fff]+", japanese_source)).strip()
    latin_candidate = re.sub(r"[\u3040-\u30ff\u3400-\u9fff]+", "", latin_source).strip()
    latin_candidate = re.sub(r"\s+", " ", latin_candidate)
    name: dict[str, str] = {"latin": latin_candidate or title}
    if kanji_match:
        name["kanji"] = kanji_match
    return name


def split_list_field(value: str) -> list[str]:
    cleaned = clean_text(value)
    if not cleaned:
        return []

    items: list[str] = []
    for piece in re.split(r"(?:\n|,|;|/)", cleaned):
        entry = piece.strip(" -*•")
        if not entry:
            continue
        if entry not in items:
            items.append(entry)
    return items


TRANSLATION_MAP = {
    " is a ": " est ",
    " in the manga and anime series ": " dans la série manga et anime ",
    " manga series ": " série manga ",
    " anime series ": " série animée ",
    " from ": " de ",
    " who plays as ": " qui joue au poste de ",
    " midfielder": " milieu",
    " defender": " défenseur",
    " forward": " attaquant",
    " goalkeeper": " gardien",
    " captain": " capitaine",
    " player": " joueur",
    " team": " équipe",
    " national team": " équipe nationale",
    " japanese": " japonais",
    " brazilian": " brésilien",
    " german": " allemand",
    " french": " français",
    " argentine": " argentin",
}


def translate_description_to_french(text: str) -> str:
    translated = clean_text(text)
    if not translated:
        return ""

    for source, target in TRANSLATION_MAP.items():
        translated = re.sub(re.escape(source), target, translated, flags=re.IGNORECASE)

    translated = re.sub(r"\s+", " ", translated).strip()
    return translated


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


def name_from_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-") if part)


def is_invalid_infobox_name(name: str) -> bool:
    return any(token in name for token in ("PAGENAME", "{{", "}}"))


def build_record(title: str, infobox: dict[str, str], description: str, image_path: str) -> dict[str, Any]:
    slug = slugify(title)
    raw_name = clean_text(infobox.get("name") or "")
    if raw_name and is_invalid_infobox_name(raw_name):
        display_name = name_from_slug(slug)
        print(f"[name-fixed-from-slug] {slug}")
    else:
        display_name = raw_name or title

    name_split = split_name_fields(infobox, display_name)
    latin_name = clean_text(name_split.get("latin") or display_name)
    japanese_name = clean_text(name_split.get("kanji") or "")
    current_teams = split_list_field(infobox.get("team", ""))
    former_teams = split_list_field(infobox.get("former_team", ""))
    teams = list(dict.fromkeys(current_teams + former_teams))
    position = clean_text(infobox.get("position", ""))
    nationality = clean_text(infobox.get("nationality", ""))
    popularity = 999

    return {
        "slug": slug,
        "name": latin_name,
        "japaneseName": japanese_name,
        "nameSplit": {
            "latin": latin_name,
            "kanji": japanese_name,
        },
        "position": position,
        "teams": teams,
        "nationality": nationality,
        "physical": parse_physical(infobox),
        "description": translate_description_to_french(description),
        "image": image_path,
        "infobox": infobox,
        "popularity": popularity,
        # Backward compatibility for existing list sorting logic.
        "popularityRank": popularity,
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

    for key in (
        "name",
        "japaneseName",
        "nameSplit",
        "position",
        "teams",
        "nationality",
        "physical",
        "description",
        "image",
        "infobox",
        "popularity",
        "popularityRank",
    ):
        if is_empty(existing.get(key)) and not is_empty(incoming.get(key)):
            existing[key] = incoming[key]
            changed = True

    if isinstance(existing.get("nameSplit"), dict) and isinstance(incoming.get("nameSplit"), dict):
        for name_key in ("latin", "kanji"):
            if is_empty(existing["nameSplit"].get(name_key)) and not is_empty(incoming["nameSplit"].get(name_key)):
                existing["nameSplit"][name_key] = incoming["nameSplit"][name_key]
                changed = True

    # Keep mirrored compatibility fields aligned when they are still empty.
    if is_empty(existing.get("name")) and not is_empty(existing.get("nameSplit", {}).get("latin")):
        existing["name"] = existing["nameSplit"]["latin"]
        changed = True
    if is_empty(existing.get("japaneseName")) and not is_empty(existing.get("nameSplit", {}).get("kanji")):
        existing["japaneseName"] = existing["nameSplit"]["kanji"]
        changed = True

    return changed


def migrate_legacy_record(record: dict[str, Any]) -> dict[str, Any]:
    infobox = record.get("infobox") if isinstance(record.get("infobox"), dict) else {}
    slug = clean_text(str(record.get("slug") or ""))

    name_split_value = record.get("nameSplit")
    if isinstance(name_split_value, dict):
        latin = clean_text(name_split_value.get("latin") or "")
        kanji = clean_text(name_split_value.get("kanji") or "")
        if latin and (not kanji):
            split_name = split_name_fields({"name": latin, "romaji": "", "japanese": ""}, latin)
            latin = clean_text(split_name.get("latin") or latin)
            kanji = clean_text(split_name.get("kanji") or "")
    elif isinstance(record.get("name"), dict):
        legacy_name = record.get("name")
        latin = clean_text(legacy_name.get("latin") or "")
        kanji = clean_text(legacy_name.get("kanji") or "")
    else:
        split_name = split_name_fields(
            {
                "name": str(record.get("name") or ""),
                "romaji": "",
                "japanese": str(record.get("japaneseName") or infobox.get("japanese") or ""),
            },
            clean_text(str(record.get("name") or name_from_slug(slug) or slug)),
        )
        latin = clean_text(split_name.get("latin") or "")
        kanji = clean_text(split_name.get("kanji") or "")

    if not latin:
        latin = clean_text(name_from_slug(slug) or slug)
    if not kanji:
        kanji = clean_text(str(record.get("japaneseName") or infobox.get("japanese") or ""))

    name_split = {"latin": latin, "kanji": kanji}

    teams_sources: list[str] = []
    for key in ("equipes", "teams", "anciennes_equipes", "former_team"):
        value = record.get(key)
        if isinstance(value, list):
            teams_sources.extend(str(item) for item in value)
    if not teams_sources:
        teams_sources = split_list_field(str(infobox.get("team") or "")) + split_list_field(str(infobox.get("former_team") or ""))

    teams = [team for i, team in enumerate(teams_sources) if clean_text(team) and team not in teams_sources[:i]]

    popularity_raw = record.get("popularity") if record.get("popularity") is not None else record.get("popularityRank")
    try:
        popularity = int(popularity_raw) if popularity_raw is not None else 999
    except (TypeError, ValueError):
        popularity = 999

    return {
        "slug": slug,
        "name": latin,
        "japaneseName": kanji,
        "nameSplit": name_split,
        "position": clean_text(str(record.get("position") or record.get("poste") or infobox.get("position") or "")),
        "teams": [clean_text(team) for team in teams if clean_text(team)],
        "nationality": clean_text(str(record.get("nationality") or record.get("nationalite") or infobox.get("nationality") or "")),
        "physical": record.get("physical") if isinstance(record.get("physical"), dict) else parse_physical(infobox),
        "description": translate_description_to_french(str(record.get("description") or "")),
        "image": str(record.get("image") or ""),
        "infobox": infobox if infobox else {key: "" for key in INFOBOX_FIELDS},
        "popularity": popularity,
        "popularityRank": popularity,
    }


def needs_refresh(existing: dict[str, Any]) -> bool:
    keys_to_check = ("name", "position", "nationality", "image")
    if any(is_empty(existing.get(key)) for key in keys_to_check):
        return True

    local_image = web_path_to_local(existing.get("image"))
    return bool(local_image and not local_image.exists())


def main() -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    existing_records = [migrate_legacy_record(record) for record in load_existing_records()]
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
    records.sort(key=lambda item: str(item.get("name") or item.get("nameSplit", {}).get("latin") or item.get("slug", "")).casefold())

    with OUTPUT_JSON.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Wrote {len(records)} records to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
