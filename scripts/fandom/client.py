from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

API_URL = "https://captaintsubasa.fandom.com/api.php"

OPENER = build_opener(ProxyHandler({}))
OPENER.addheaders = [("User-Agent", "journaldegaspard-sync-entities/1.0")]


def api_get_json(params: dict[str, Any]) -> dict[str, Any]:
    query = urlencode(params)
    request = Request(f"{API_URL}?{query}")
    try:
        with OPENER.open(request, timeout=40) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"API request failed: {exc}") from exc


def fetch_category_titles(category_title: str) -> list[str]:
    titles: list[str] = []
    params: dict[str, Any] = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category_title,
        "cmlimit": "500",
        "format": "json",
    }

    while True:
        payload = api_get_json(params)
        members = payload.get("query", {}).get("categorymembers", [])
        titles.extend(str(member.get("title", "")).strip() for member in members)

        continuation = payload.get("continue")
        if not continuation:
            break
        params.update(continuation)

    return [title for title in titles if title and not title.startswith(("Category:", "Template:", "File:"))]


def fetch_page_wikitext(title: str) -> str:
    payload = api_get_json(
        {
            "action": "parse",
            "page": title,
            "prop": "wikitext",
            "format": "json",
        }
    )
    return payload.get("parse", {}).get("wikitext", {}).get("*", "")


def fetch_intro_extract(title: str) -> str:
    payload = api_get_json(
        {
            "action": "query",
            "prop": "extracts",
            "titles": title,
            "exintro": "1",
            "plaintext": "1",
            "format": "json",
        }
    )
    pages = payload.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), {})
    return str(page.get("extract", "") or "").strip()


def fetch_page_links(title: str) -> list[str]:
    links: list[str] = []
    params: dict[str, Any] = {
        "action": "parse",
        "page": title,
        "prop": "links",
        "format": "json",
    }

    while True:
        payload = api_get_json(params)
        links.extend(str(link.get("*", "")).strip() for link in payload.get("parse", {}).get("links", []))

        continuation = payload.get("continue")
        if not continuation:
            break
        params.update(continuation)

    return [item for item in links if item and not item.startswith(("Category:", "Template:", "File:"))]
