#!/usr/bin/env python3
"""Enrich character data with teams and techniques from Captain Tsubasa Fandom."""

from __future__ import annotations

import json
from itertools import permutations
from pathlib import Path
from typing import Any

from fandom.client import (
    fetch_category_titles,
    fetch_page_links,
    fetch_page_wikitext,
)

from fandom.extract_teams import (
    extract_team_candidates_from_page_links,
    extract_teams_from_infobox,
    fetch_team_details,
)

from fandom.extract_techniques import (
    build_technique_to_users_map,
    extract_techniques_from_infobox,
    fetch_character_technique_pages,
    fetch_technique_catalog,
    fetch_technique_details,
)

from fandom.normalize import (
    classify_team,
    extract_infobox_fields,
    infer_parent_team,
    normalize_entity_name,
    slugify,
)

from fandom.relations import (
    character_ref,
    entity_ref,
    sort_entities,
)

from fandom.writers import safe_write_non_empty_list


PERSONNAGES_JSON = Path("assets/data/personnages.json")
EQUIPES_JSON = Path("assets/data/equipes.json")
TECHNIQUES_JSON = Path("assets/data/techniques.json")
DUEL_ROSTER_JSON = Path("assets/data/duel-roster.json")
DUEL_ADVERSAIRES_JSON = Path("assets/data/duel-adversaires.json")

# Les trois postes d'une équipe du mode Équipe, dans l'ordre.
FAMILLES_DUEL = ("tir", "construction", "defense")

TEAM_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------

def load_personnages() -> list[dict[str, Any]]:
    with PERSONNAGES_JSON.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise RuntimeError("assets/data/personnages.json must contain a list")

    return [entry for entry in payload if isinstance(entry, dict)]


def dedupe_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}

    for ref in refs:
        slug = str(ref.get("slug", "")).strip()

        if not slug:
            continue

        previous = unique.get(slug)

        if not previous:
            unique[slug] = ref
            continue

        prev_conf = str(previous.get("confidence", "medium"))
        new_conf = str(ref.get("confidence", "medium"))

        if TEAM_CONFIDENCE_ORDER.get(new_conf, 0) >= TEAM_CONFIDENCE_ORDER.get(prev_conf, 0):
            unique[slug] = ref

    return sort_entities(list(unique.values()))


def validate_team_membership(team_name: str, character_name: str) -> bool:
    try:
        wikitext = fetch_page_wikitext(team_name)
    except Exception:
        return False

    return character_name.lower() in wikitext.lower()


def poste_de(record: dict[str, Any]) -> str:
    """
    Ramène le poste brut du Fandom à un libellé FR.

    Le champ est une concaténation d'infobox ("Attacking midfielderForward") :
    on retient le premier poste reconnu.
    """
    valeur = str(record.get("position") or record.get("poste") or "").lower()

    for cle, libelle in (
        ("goalkeeper", "Gardien"),
        ("defender", "Défenseur"),
        ("midfielder", "Milieu"),
        ("forward", "Attaquant"),
    ):
        if cle in valeur:
            return libelle

    return "Autre"


def construire_roster_duel(
    personnages: list[dict[str, Any]],
    techniques: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Construit le vivier du mode Équipe du duel.

    Un personnage y figure s'il possède au moins une technique rattachée à une
    famille de jeu. Pour chaque famille, on retient sa technique la plus
    personnelle — celle qui compte le moins d'utilisateurs. La rareté sert donc
    de courbe de puissance sans donnée supplémentaire.

    La technique dépend du poste occupé, et non du personnage seul : Wakabayashi
    défend avec « Uppercut Defense » mais construirait avec « Birdcage ». Sans
    ça, la sélection automatique le rangerait en construction, ce qui est un
    contresens pour un gardien.

    Ce fichier dérivé évite au serveur du duel de charger personnages.json
    (330 Ko) et techniques.json à chaque composition d'équipe.
    """
    par_slug = {t["slug"]: t for t in techniques}
    roster: list[dict[str, Any]] = []

    for record in personnages:
        familles: dict[str, dict[str, Any]] = {}

        for reference in record.get("techniques") or []:
            technique = par_slug.get(str(reference.get("slug", "")))

            if not technique:
                continue

            popularite = len(technique.get("users") or [])

            for famille in technique.get("familles") or []:
                retenue = familles.get(famille)

                if retenue is None or popularite < retenue["_utilisateurs"]:
                    familles[famille] = {
                        "technique": technique["name"],
                        "slug": technique["slug"],
                        "effet": (technique.get("effets") or {}).get(famille, ""),
                        "description": technique.get("description", ""),
                        "_utilisateurs": popularite,
                    }

        if not familles:
            continue

        for entree in familles.values():
            entree.pop("_utilisateurs", None)

        roster.append({
            "slug": record["slug"],
            "nom": record.get("name", record["slug"]),
            "image": record.get("image", ""),
            "poste": poste_de(record),
            "familles": familles,
        })

    return sorted(roster, key=lambda entry: str(entry["nom"]).lower())


def construire_adversaires_duel(
    equipes: list[dict[str, Any]],
    roster: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Recense les équipes réelles que l'ordinateur peut aligner dans le duel.

    Une équipe est retenue si trois de ses joueurs distincts couvrent les trois
    familles. La contrainte est moins sévère qu'il n'y paraît : sur les équipes
    écartées, presque toutes le sont faute de trois personnages jouables, et
    non par déséquilibre des familles.

    Ce fichier dérivé évite au serveur du duel de charger equipes.json (104 Ko)
    pour composer l'équipe adverse.
    """
    jouables = {p["slug"] for p in roster}
    par_slug = {p["slug"]: p for p in roster}
    adversaires: list[dict[str, Any]] = []

    for equipe in equipes:
        effectif = [j["slug"] for j in equipe.get("players", []) if j["slug"] in jouables]

        if len(effectif) < len(FAMILLES_DUEL):
            continue

        # L'effectif est trop petit pour justifier autre chose qu'un parcours
        # exhaustif des trios possibles.
        composable = any(
            all(FAMILLES_DUEL[rang] in par_slug[slug]["familles"] for rang, slug in enumerate(trio))
            for trio in permutations(effectif, len(FAMILLES_DUEL))
        )

        if not composable:
            continue

        adversaires.append({
            "slug": equipe["slug"],
            "nom": equipe["name"],
            "type": equipe.get("type", ""),
            "effectif": sorted(effectif),
        })

    return sorted(adversaires, key=lambda entry: -len(entry["effectif"]))


def is_invalid_team_name(name: str) -> bool:
    lowered = name.lower()

    invalid_keywords = [
        "film",
        "movie",
        "episode",
        "captain tsubasa:",
        "game",
        "ronc",
        "challenge",
        "tournament",
    ]

    return any(k in lowered for k in invalid_keywords)


# ------------------------------------------------------------
# Main pipeline
# ------------------------------------------------------------

def main() -> None:

    personnages = load_personnages()

    if not personnages:
        raise RuntimeError("No characters available")

    category_titles = fetch_category_titles("Category:Characters")

    title_by_slug = {
        slugify(title.split("/", 1)[0].strip()):
        title.split("/", 1)[0].strip()
        for title in category_titles
    }

    known_character_titles = set(title_by_slug.values())

    team_links_by_character: dict[str, list[dict[str, Any]]] = {}
    technique_links_by_character: dict[str, list[str]] = {}

    print(f"[info] loaded {len(personnages)} characters")
    print(f"[info] found {len(title_by_slug)} Fandom character titles")

    for record in personnages:

        slug = str(record.get("slug", "")).strip()

        if not slug:
            continue

        title = title_by_slug.get(slug)

        if not title:
            continue

        try:
            wikitext = fetch_page_wikitext(title)
            page_links = fetch_page_links(title)
        except RuntimeError:
            continue

        infobox = extract_infobox_fields(wikitext)

        extracted_team_refs: list[dict[str, Any]] = []

        for team in extract_teams_from_infobox(infobox):

            if is_invalid_team_name(team):
                continue

            extracted_team_refs.append({
                "name": team,
                "confidence": "high",
            })

        if not extracted_team_refs:

            team_candidates = extract_team_candidates_from_page_links(
                page_links,
                known_character_titles,
            )

            for team in team_candidates:

                if is_invalid_team_name(team):
                    continue

                if validate_team_membership(team, title):
                    confidence = "medium"
                else:
                    confidence = "low"

                extracted_team_refs.append({
                    "name": team,
                    "confidence": confidence,
                })

        if extracted_team_refs:

            team_links_by_character[slug] = dedupe_refs(
                [
                    {
                        **entity_ref(team_ref["name"], "equipe"),
                        "confidence": team_ref["confidence"],
                    }
                    for team_ref in extracted_team_refs
                ]
            )

        techniques = extract_techniques_from_infobox(infobox)

        if techniques:
            technique_links_by_character[slug] = techniques

    # Le catalogue des catégories du wiki fait autorité : tout ce qui n'y
    # figure pas n'est pas une technique, quelle que soit sa provenance.
    technique_catalog = fetch_technique_catalog()

    print(f"[info] technique catalog: {len(technique_catalog)} entries")

    # L'infobox des personnages cite des noms libres : on ne garde que ceux
    # qui correspondent à une technique du catalogue.
    for character_slug, names in list(technique_links_by_character.items()):
        technique_links_by_character[character_slug] = [
            technique_catalog[slugify(name)]["nom"]
            for name in names
            if slugify(name) in technique_catalog
        ]

    technique_to_users = build_technique_to_users_map(
        fetch_character_technique_pages(),
        known_character_titles,
        technique_catalog,
    )

    for technique_title, user_titles in technique_to_users.items():

        technique_name = normalize_entity_name(technique_title)

        if not technique_name:
            continue

        for user_title in user_titles:

            user_slug = slugify(user_title)

            technique_links_by_character.setdefault(user_slug, [])

            if technique_name not in technique_links_by_character[user_slug]:
                technique_links_by_character[user_slug].append(technique_name)

    characters_with_teams = sum(1 for v in team_links_by_character.values() if v)
    characters_with_techniques = sum(1 for v in technique_links_by_character.values() if v)

    print(f"[info] characters with teams extracted: {characters_with_teams}")
    print(f"[info] characters with techniques extracted: {characters_with_techniques}")

    teams_payload: dict[str, dict[str, Any]] = {}
    techniques_payload: dict[str, dict[str, Any]] = {}

    # Le catalogue amorce la charge utile : une technique existe parce que le
    # wiki la recense, pas parce qu'un personnage s'y rattache. Sans cela, les
    # techniques que nulle page /Techniques ne cite resteraient absentes.
    for technique_slug, entree in technique_catalog.items():
        technique_name = entree["nom"]

        techniques_payload[technique_slug] = {
            "slug": technique_slug,
            "name": technique_name,
            "url": entity_ref(technique_name, "technique")["url"],
            "japanese_name": "",
            "first_appearance": "",
            "description": "",
            "image": "",
            # Familles de jeu du duel, déduites des catégories du wiki.
            "familles": list(entree["familles"]),
            "effets": dict(entree["effets"]),
            "users": [],
        }

    for record in personnages:

        slug = str(record.get("slug", "")).strip()

        if not slug:
            continue

        linked_team_refs = team_links_by_character.get(slug, [])

        linked_technique_refs = [
            entity_ref(t, "technique")
            for t in technique_links_by_character.get(slug, [])
        ]

        teams_initial = dedupe_refs(linked_team_refs)

        filtered_team_refs: list[dict[str, Any]] = []

        character_pointer = character_ref(record)

        for team_ref in teams_initial:

            confidence = str(team_ref.get("confidence", "low"))

            if confidence not in ("high", "medium"):
                continue

            team_name = team_ref["name"] or team_ref["slug"]

            if is_invalid_team_name(team_name):
                continue

            classification = classify_team(team_name)

            if classification["type"] == "competition":
                continue

            filtered_team_refs.append(team_ref)

            team_slug = team_ref["slug"]

            if team_slug not in teams_payload:

                parent_team = infer_parent_team(team_name)

                teams_payload[team_slug] = {
                    "slug": team_ref["slug"],
                    "name": team_ref["name"],
                    "type": classification["type"],
                    "age_category": classification["age_category"],
                    "parent_team": parent_team,
                    "url": team_ref["url"],
                    "japanese_name": "",
                    "description": "",
                    "image": "",
                    "players": [],
                }

            teams_payload[team_slug]["players"].append(character_pointer)

        record["teams"] = dedupe_refs(filtered_team_refs)

        record["techniques"] = dedupe_refs(linked_technique_refs)

        for technique_ref in record["techniques"]:

            technique = techniques_payload.get(technique_ref["slug"])

            # Le catalogue a déjà créé toutes les techniques légitimes : une
            # référence inconnue ici est un reliquat, on ne la ressuscite pas.
            if technique is not None:
                technique["users"].append(character_pointer)

    equipes = sort_entities([
        {
            **team,
            "players": dedupe_refs(team.get("players", [])),
        }
        for team in teams_payload.values()
    ])

    techniques = sort_entities([
        {
            **technique,
            "users": dedupe_refs(technique.get("users", [])),
        }
        for technique in techniques_payload.values()
    ])

    for index, equipe in enumerate(equipes, start=1):
        equipe.update(fetch_team_details(equipe["name"]))

        if index % 25 == 0:
            print(f"[info] team details fetched: {index}/{len(equipes)}")

    for index, technique in enumerate(techniques, start=1):
        technique.update(fetch_technique_details(technique["name"]))

        if index % 25 == 0:
            print(f"[info] technique details fetched: {index}/{len(techniques)}")

    personnages_sorted = sorted(
        personnages,
        key=lambda entry: (
            int(entry.get("popularity", 999)),
            str(entry.get("name", "")).lower(),
        ),
    )

    roster_duel = construire_roster_duel(personnages_sorted, techniques)
    adversaires_duel = construire_adversaires_duel(equipes, roster_duel)

    safe_write_non_empty_list(EQUIPES_JSON, equipes, minimum_items=1, label="equipes.json")
    safe_write_non_empty_list(TECHNIQUES_JSON, techniques, minimum_items=1, label="techniques.json")
    safe_write_non_empty_list(PERSONNAGES_JSON, personnages_sorted, minimum_items=50, label="personnages.json")
    safe_write_non_empty_list(DUEL_ROSTER_JSON, roster_duel, minimum_items=20, label="duel-roster.json")
    safe_write_non_empty_list(DUEL_ADVERSAIRES_JSON, adversaires_duel, minimum_items=5, label="duel-adversaires.json")

    print(f"[ok] wrote {len(roster_duel)} duel roster entries")
    print(f"[ok] wrote {len(adversaires_duel)} duel opponents")
    print(f"[ok] wrote {len(equipes)} teams")
    print(f"[ok] wrote {len(techniques)} techniques")
    print(f"[ok] updated {len(personnages_sorted)} characters")


if __name__ == "__main__":
    main()
