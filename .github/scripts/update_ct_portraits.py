#!/usr/bin/env python3
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

API_BASE = "https://captaintsubasa.fandom.com/api.php"
CATEGORY_URL = (
    f"{API_BASE}?action=query&list=categorymembers&"
    "cmtitle=Category:Characters&cmlimit=500&format=json"
)
OUTPUT_DIR = Path("assets/images/olive-et-tom")
JS_FILE = Path("assets/js/personnages.js")
LOCAL_PREFIX = "assets/images/olive-et-tom"


def fetch_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "journaldegaspard-bot/1.0"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "journaldegaspard-bot/1.0"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    lowered = lowered.replace("_", "-")
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = re.sub(r"-+", "-", lowered).strip("-")
    return lowered or "unknown"


def get_titles() -> list[str]:
    data = fetch_json(CATEGORY_URL)
    members = data.get("query", {}).get("categorymembers", [])
    titles = [m.get("title", "").strip() for m in members if m.get("title")]
    return sorted(set(titles))


def get_original_image_url(page_title: str) -> str | None:
    encoded_title = quote(page_title, safe="")
    url = (
        f"{API_BASE}?action=query&titles={encoded_title}&"
        "prop=pageimages&piprop=original&format=json"
    )
    data = fetch_json(url)
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        original = page.get("original", {})
        source = original.get("source")
        if source:
            return source
    return None


def update_character_images(slug_by_title: dict[str, str]) -> None:
    content = JS_FILE.read_text(encoding="utf-8")

    object_pattern = re.compile(r"\{(?:[^{}]|\{[^{}]*\})*\}", re.DOTALL)

    def replace_object(match: re.Match) -> str:
        block = match.group(0)
        japanese_match = re.search(r'japaneseName:\s*"([^"]+)"', block)
        name_match = re.search(r'name:\s*"([^"]+)"', block)

        title_candidates = []
        if japanese_match:
            japanese_name = japanese_match.group(1).strip()
            title_candidates.extend(
                [japanese_name, japanese_name.replace(" ", "_")]
            )
        if name_match:
            name = name_match.group(1).strip()
            title_candidates.extend([name, name.replace(" ", "_")])

        slug = None
        for title in title_candidates:
            if title in slug_by_title:
                slug = slug_by_title[title]
                break
        if not slug:
            return block

        new_image_line = f'image: "../../{LOCAL_PREFIX}/{slug}.png"'
        updated = re.sub(r'image:\s*"[^"]*"', new_image_line, block, count=1)
        return updated

    updated_content = object_pattern.sub(replace_object, content)
    JS_FILE.write_text(updated_content, encoding="utf-8")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    titles = get_titles()
    if not titles:
        print("No character titles returned by API.", file=sys.stderr)
        return 1

    slug_by_title: dict[str, str] = {}

    for title in titles:
        slug = slugify(title)
        filename = f"{slug}.png"
        slug_by_title[title] = slug

        try:
            source = get_original_image_url(title)
            if not source:
                print(f"Skipping {title}: no image found")
                continue

            print(f"Downloading {title} → {filename}")
            image_bytes = fetch_bytes(source)
            (OUTPUT_DIR / filename).write_bytes(image_bytes)
        except Exception as exc:
            print(f"Skipping {title}: {exc}", file=sys.stderr)

    update_character_images(slug_by_title)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
