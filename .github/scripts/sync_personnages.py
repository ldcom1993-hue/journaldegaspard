#!/usr/bin/env python3

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

API = "https://captaintsubasa.fandom.com/api.php"

JS_FILE = Path("assets/js/personnages.js")
JSON_FILE = Path("assets/data/personnages.json")
IMG_DIR = Path("assets/images/olive-et-tom")

HEADERS = {
    "User-Agent": "journaldegaspard-bot/1.0"
}


# --------------------------------------------------
# HTTP helpers
# --------------------------------------------------

def fetch_json(url):
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def fetch_bytes(url):
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=60) as r:
        return r.read()


# --------------------------------------------------
# slug helpers
# --------------------------------------------------

def slug_to_search(slug):
    return slug.replace("-", " ") + " captain tsubasa"


def slug_to_filename(slug):
    return f"{slug}.png"


# --------------------------------------------------
# fandom API
# --------------------------------------------------

def search_title(slug):
    query = quote(slug_to_search(slug))
    url = f"{API}?action=query&list=search&srsearch={query}&format=json"
    data = fetch_json(url)

    results = data.get("query", {}).get("search", [])

    if not results:
        return None

    return results[0]["title"]


def get_infobox(title):

    url = f"{API}?action=parse&page={quote(title)}&prop=wikitext&format=json"
    data = fetch_json(url)

    text = data["parse"]["wikitext"]["*"]

    fields = {}

    for key in [
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
    ]:

        m = re.search(rf"\|\s*{key}\s*=\s*(.+)", text)

        if m:
            value = m.group(1)
            value = re.sub(r"\[\[|\]\]", "", value)
            value = value.strip()
            fields[key] = value

    return fields


def get_description(title):

    url = (
        f"{API}?action=query&prop=extracts&exintro=1"
        f"&titles={quote(title)}&format=json"
    )

    data = fetch_json(url)

    pages = data["query"]["pages"]

    for page in pages.values():
        text = page.get("extract", "")
        text = re.sub("<.*?>", "", text)
        return text.strip()

    return ""


def get_image(title):

    url = (
        f"{API}?action=query&titles={quote(title)}"
        "&prop=pageimages&piprop=original&format=json"
    )

    data = fetch_json(url)

    pages = data["query"]["pages"]

    for page in pages.values():
        if "original" in page:
            return page["original"]["source"]

    return None


# --------------------------------------------------
# parse JS characters safely
# --------------------------------------------------

def extract_slugs():

    content = JS_FILE.read_text(encoding="utf-8")

    return re.findall(
        r"/personnages/([a-z0-9\-]+)\.html",
        content,
    )


# --------------------------------------------------
# JSON generation
# --------------------------------------------------

def build_json():

    characters = []

    for slug in extract_slugs():

        print("Processing", slug)

        title = search_title(slug)

        if not title:
            print("No fandom page")
            continue

        info = get_infobox(title)

        desc = get_description(title)

        img_url = get_image(title)

        if img_url:

            filename = slug_to_filename(slug)

            path = IMG_DIR / filename

            if not path.exists():

                print("Downloading image")

                path.write_bytes(fetch_bytes(img_url))

        teams = []

        for key in [
            "team",
            "club",
            "affiliation",
            "former_team",
        ]:

            if key in info:
                teams.append(info[key])

        character = {

            "slug": slug,
            "name": info.get("name", title),
            "japaneseName": info.get("romaji", info.get("japanese", "")),
            "position": info.get("position", ""),
            "teams": teams,
            "nationality": info.get("nationality", ""),
            "description": desc,
            "image": f"/assets/images/olive-et-tom/{slug}.png",
            "fandomTitle": title,
            "infobox": info,

        }

        characters.append(character)

    JSON_FILE.parent.mkdir(parents=True, exist_ok=True)

    JSON_FILE.write_text(
        json.dumps(characters, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return characters


# --------------------------------------------------
# JS correction
# --------------------------------------------------

def update_js(characters):

    content = JS_FILE.read_text(encoding="utf-8")

    for c in characters:

        slug = c["slug"]

        image = c["image"]

        japanese = c["japaneseName"]

        teams = ", ".join(c["teams"])

        desc = c["description"][:300]

        content = re.sub(
            rf'(link:\s*"/univers/olive-et-tom/personnages/{slug}\.html",)'
            r'.*?image:\s*"[^"]*"',
            rf'\1\n    image: "{image}"',
            content,
            flags=re.DOTALL,
        )

        content = re.sub(
            rf'(link:\s*"/univers/olive-et-tom/personnages/{slug}\.html",)'
            r'.*?japaneseName:\s*"[^"]*"',
            rf'\1\n    japaneseName: "{japanese}"',
            content,
            flags=re.DOTALL,
        )

        content = re.sub(
            rf'(link:\s*"/univers/olive-et-tom/personnages/{slug}\.html",)'
            r'.*?team:\s*"[^"]*"',
            rf'\1\n    team: "{teams}"',
            content,
            flags=re.DOTALL,
        )

        content = re.sub(
            rf'(link:\s*"/univers/olive-et-tom/personnages/{slug}\.html",)'
            r'.*?description:\s*"[^"]*"',
            rf'\1\n    description: "{desc}"',
            content,
            flags=re.DOTALL,
        )

    JS_FILE.write_text(content, encoding="utf-8")


# --------------------------------------------------
# main
# --------------------------------------------------

def main():

    IMG_DIR.mkdir(parents=True, exist_ok=True)

    characters = build_json()

    update_js(characters)

    print("Done")


if __name__ == "__main__":
    main()
