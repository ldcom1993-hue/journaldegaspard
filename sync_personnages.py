#!/usr/bin/env python3
"""Sync Captain Tsubasa characters from Fandom into local JSON/images.

Source of truth: Fandom Category:Characters API.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import requests

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
    "club",
    "affiliation",
    "former_team",
    "nationality",
    "status",
    "occupation",
]


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text.lower()).strip("-")
    return cleaned or "character"


def fetch_category_titles(session: requests.Session) -> list[str]:
    titles: list[str] = []
    params: dict[str, Any] = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": CATEGORY_TITLE,
        "cmlimit": "500",
        "format": "json",
    }

    while True:
        response = session.get(API_URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()

        members = payload.get("query", {}).get("categorymembers", [])
        titles.extend(member["title"] for member in members if "title" in member)

        if "continue" not in payload:
            break

        params.update(payload["continue"])

    return titles


def extract_character_infobox(wikitext: str) -> str:
    start = re.search(r"\{\{\s*[^\n\|\}]*character[^\n\}]*", wikitext, flags=re.IGNORECASE)
    if not start:
        return ""

    i = start.start()
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
                return wikitext[start.start() : i]
            continue
        i += 1

    return ""


def extract_infobox_fields(wikitext: str) -> dict[str, str]:
    infobox_text = extract_character_infobox(wikitext)
    results: dict[str, str] = {key: "" for key in INFOBOX_FIELDS}

    if not infobox_text:
        return results

    for field in INFOBOX_FIELDS:
        match = re.search(rf"(?im)^\|\s*{re.escape(field)}\s*=\s*(.*)$", infobox_text)
        if match:
            results[field] = match.group(1).strip()

    return results


def clean_description(extract_html: str) -> str:
    text = re.sub(r"<[^>]+>", "", extract_html or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_character_payload(session: requests.Session, title: str) -> tuple[dict[str, str], str, str | None]:
    parse_params = {
        "action": "parse",
        "page": title,
        "prop": "wikitext",
        "format": "json",
    }
    parse_response = session.get(API_URL, params=parse_params, timeout=30)
    parse_response.raise_for_status()
    parse_payload = parse_response.json()
    wikitext = parse_payload.get("parse", {}).get("wikitext", {}).get("*", "")
    infobox = extract_infobox_fields(wikitext)

    query_params = {
        "action": "query",
        "prop": "extracts|pageimages",
        "titles": title,
        "exintro": "1",
        "explaintext": "0",
        "piprop": "original",
        "format": "json",
    }
    query_response = session.get(API_URL, params=query_params, timeout=30)
    query_response.raise_for_status()
    query_payload = query_response.json()
    pages = query_payload.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), {})

    description = clean_description(page.get("extract", ""))
    image_url = page.get("original", {}).get("source")

    return infobox, description, image_url


def maybe_download_image(session: requests.Session, slug: str, image_url: str | None) -> str:
    image_path = IMAGE_DIR / f"{slug}.png"
    if image_path.exists():
        print(f"Skipped existing image {slug}")
        return f"/{image_path.as_posix()}"

    if not image_url:
        return ""

    image_response = session.get(image_url, timeout=60)
    image_response.raise_for_status()
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(image_response.content)
    print(f"Downloaded image {slug}")
    return f"/{image_path.as_posix()}"


def build_character_record(title: str, slug: str, infobox: dict[str, str], description: str, image: str) -> dict[str, Any]:
    teams = [value for value in (infobox.get("team", ""), infobox.get("club", ""), infobox.get("former_team", "")) if value]
    return {
        "slug": slug,
        "name": title,
        "japaneseName": infobox.get("japanese", ""),
        "position": infobox.get("position", ""),
        "teams": teams,
        "nationality": infobox.get("nationality", ""),
        "description": description,
        "image": image,
        "infobox": infobox,
    }


def main() -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    with requests.Session() as session:
        session.headers.update({"User-Agent": "journaldegaspard-sync/1.0"})

        titles = fetch_category_titles(session)
        print(f"Found {len(titles)} characters")

        characters: list[dict[str, Any]] = []

        for title in titles:
            slug = slugify(title)
            infobox, description, image_url = fetch_character_payload(session, title)
            image = maybe_download_image(session, slug, image_url)
            characters.append(build_character_record(title, slug, infobox, description, image))

    characters.sort(key=lambda c: c["name"].casefold())

    with OUTPUT_JSON.open("w", encoding="utf-8") as file:
        json.dump(characters, file, ensure_ascii=False, indent=2)
        file.write("\n")


if __name__ == "__main__":
    main()
