from __future__ import annotations

import json
import re
from pathlib import Path

from fandom.client import (
    fetch_category_titles,
    fetch_page_wikitext
)

from fandom.normalize import slugify, normalize_entity_name

PERSONNAGES_JSON = Path("assets/data/personnages.json")
EQUIPES_JSON = Path("assets/data/equipes.json")


TEAM_CATEGORIES = [
    "Category:Teams",
    "Category:School Teams",
    "Category:National Teams",
    "Category:Club Teams",
]


PLAYER_SECTION_KEYWORDS = (
    "players",
    "members",
    "team members",
    "current squad",
    "former players"
)


def load_personnages():

    with PERSONNAGES_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def extract_links(text):

    return re.findall(r"\[\[([^\]]+)\]\]", text)


def extract_players_from_wikitext(text, known_characters):

    players = []

    links = extract_links(text)

    for link in links:

        name = link.split("|")[0].strip()

        if name in known_characters:
            players.append(name)

    return players


def detect_player_sections(wikitext):

    sections = re.split(r"==+[^=]+==+", wikitext)

    player_sections = []

    for section in sections:

        lowered = section.lower()

        if any(k in lowered for k in PLAYER_SECTION_KEYWORDS):

            player_sections.append(section)

    return player_sections


def extract_team_roster(team_title, known_characters):

    try:

        wikitext = fetch_page_wikitext(team_title)

    except Exception:

        return []

    sections = detect_player_sections(wikitext)

    players = []

    for section in sections:

        players.extend(
            extract_players_from_wikitext(section, known_characters)
        )

    return list(set(players))


def main():

    personnages = load_personnages()

    character_names = {
        p["name"] for p in personnages
    }

    team_titles = []

    for category in TEAM_CATEGORIES:

        try:

            team_titles.extend(
                fetch_category_titles(category)
            )

        except Exception:

            continue

    team_titles = list(set(team_titles))

    print(f"[info] team pages discovered: {len(team_titles)}")

    team_rosters = {}

    for team in team_titles:

        players = extract_team_roster(
            team,
            character_names
        )

        if not players:
            continue

        team_rosters[team] = players

    print(f"[info] teams with players: {len(team_rosters)}")

    equipes = []

    for team, players in team_rosters.items():

        equipes.append({

            "slug": slugify(team),

            "name": normalize_entity_name(team),

            "players": players

        })

    with EQUIPES_JSON.open("w", encoding="utf-8") as f:

        json.dump(equipes, f, indent=2, ensure_ascii=False)

    print(f"[ok] wrote {len(equipes)} teams")


if __name__ == "__main__":

    main()
