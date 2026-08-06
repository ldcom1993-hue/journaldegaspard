from __future__ import annotations

import re
from typing import Any

from .client import fetch_category_titles, fetch_page_links, fetch_page_wikitext_and_html
from .normalize import (
    clean_text,
    extract_infobox_fields,
    extract_japanese_name,
    first_paragraph_from_html,
    normalize_entity_name,
    split_list_field,
    slugify,
    strip_template_residue,
)

TECHNIQUE_INFOBOX_FIELDS = (
    "technique",
    "techniques",
    "special_technique",
    "special_move",
    "special_moves",
    "move",
    "moves",
    "shot",
    "skills",
)

TECHNIQUE_CATEGORY_CANDIDATES = (
    "Category:List of techniques",
)

# Les catégories du wiki qui recensent de vraies techniques. Elles font
# autorité : une page hors de ces catégories n'est pas une technique.
#
# Sans cet ancrage, on ne disposait que des liens présents sur les pages
# <Personnage>/Techniques, où figurent aussi bien des coéquipiers que des
# clubs ou des tomes du manga — d'où des « techniques » nommées AC Reggiana
# ou Captain Tsubasa (1981). Le nom du template ne permet pas de trancher :
# une vraie technique utilise « Infobox character », comme un personnage.
# Chaque catégorie se projette sur l'un des trois coups du duel, et sur l'effet
# que la technique y produit. Le duel lit ces deux informations ; les
# construire ici ne coûte rien, puisque le catalogue parcourt déjà ces
# catégories une à une pour savoir ce qui est une technique.
#
# Une même technique peut relever de deux familles : elle est alors jouable à
# deux postes, avec l'effet correspondant au poste choisi.
CATEGORIE_FAMILLE = {
    "Ground shots": ("tir", "frappe"),
    "Aerial shots": ("tir", "volee"),
    "Passes": ("construction", "une-deux"),
    "Cooperative tactics": ("construction", "une-deux"),
    "Tactics and skills": ("construction", "une-deux"),
    "Dribbles and feints": ("construction", "crochet"),
    "Saves": ("defense", "parade"),
    "Defensive techniques": ("defense", "repli"),
}

TECHNIQUE_CATEGORIES = (
    "Category:Ground shots",
    "Category:Aerial shots",
    "Category:Dribbles and feints",
    "Category:Cooperative tactics",
    "Category:Defensive techniques",
    "Category:Passes",
    "Category:Saves",
    "Category:Tactics and skills",
)


def extract_techniques_from_infobox(infobox: dict[str, str]) -> list[str]:
    techniques: list[str] = []
    for field in TECHNIQUE_INFOBOX_FIELDS:
        for candidate in split_list_field(infobox.get(field, "")):
            normalized = normalize_entity_name(candidate)
            if normalized and normalized not in techniques:
                techniques.append(normalized)
    return techniques


def _character_title_from_techniques_page(title: str) -> str | None:
    cleaned = clean_text(title)
    if not cleaned:
        return None

    if not cleaned.endswith("/Techniques"):
        return None

    character_title = cleaned[: -len("/Techniques")].strip()
    return character_title or None


def fetch_character_technique_pages() -> list[str]:
    """Recense les pages <Personnage>/Techniques, source des relations."""
    titles: list[str] = []
    for category in TECHNIQUE_CATEGORY_CANDIDATES:
        try:
            candidates = fetch_category_titles(category)
        except RuntimeError:
            continue

        for title in candidates:
            if title not in titles:
                titles.append(title)

    return titles


def fetch_technique_catalog() -> dict[str, dict[str, Any]]:
    """
    Recense les techniques réelles, indexées par slug.

    Chaque entrée retient les catégories qui l'ont fait entrer au catalogue,
    et les familles de jeu qui s'en déduisent. Ces catégories étaient
    auparavant jetées une fois le filtrage fait, alors que le duel en a besoin
    pour savoir à quel poste une technique se joue et quel effet elle produit.

    Les sous-pages (« Drive Shot/Variations ») sont écartées : ce sont des
    annexes d'une technique déjà présente, pas des techniques distinctes.

    @return slug => {nom, categories[], familles[], effets{famille: effet}}
    """
    catalog: dict[str, dict[str, Any]] = {}

    for category in TECHNIQUE_CATEGORIES:
        try:
            titles = fetch_category_titles(category)
        except RuntimeError:
            continue

        libelle = category.replace("Category:", "")
        famille, effet = CATEGORIE_FAMILLE.get(libelle, (None, None))

        for title in titles:
            cleaned = clean_text(title)

            if not cleaned or "/" in cleaned:
                continue

            entree = catalog.setdefault(
                slugify(cleaned),
                {"nom": cleaned, "categories": [], "familles": [], "effets": {}},
            )

            if libelle not in entree["categories"]:
                entree["categories"].append(libelle)

            if famille and famille not in entree["familles"]:
                entree["familles"].append(famille)

            # Première catégorie rencontrée pour cette famille : c'est elle qui
            # fixe l'effet. L'ordre de TECHNIQUE_CATEGORIES rend le résultat
            # déterminant d'une exécution à l'autre.
            if famille and famille not in entree["effets"]:
                entree["effets"][famille] = effet

    return catalog


def fetch_technique_details(title: str) -> dict[str, str]:
    """
    Lit la fiche d'une technique : introduction, nom japonais, première
    apparition. Cette page n'était jamais consultée jusqu'ici, ce qui
    laissait description et image vides sur la totalité du catalogue.
    """
    try:
        wikitext, html_text = fetch_page_wikitext_and_html(title)
    except RuntimeError:
        return {"description": "", "japanese_name": "", "first_appearance": ""}

    infobox = extract_infobox_fields(wikitext)

    return {
        "description": first_paragraph_from_html(html_text),
        "japanese_name": extract_japanese_name(infobox.get("name", "")),
        "first_appearance": strip_template_residue(infobox.get("first_appearance", "")),
    }


def build_technique_to_users_map(
    technique_page_titles: list[str],
    known_character_titles: set[str],
    catalog: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    """
    Relie chaque technique aux personnages qui l'emploient, en parcourant les
    pages <Personnage>/Techniques. Seuls les liens présents au catalogue sont
    retenus : c'est ce qui écarte coéquipiers, clubs et tomes du manga.
    """
    technique_to_users: dict[str, list[str]] = {}
    known_character_slugs = {slugify(title): title for title in known_character_titles}

    for title in technique_page_titles:
        character_title = _character_title_from_techniques_page(title)
        if not character_title:
            continue

        character_slug = slugify(character_title)
        canonical_character_title = known_character_slugs.get(character_slug)
        if not canonical_character_title:
            continue

        try:
            links = fetch_page_links(title)
        except RuntimeError:
            continue

        for linked_title in links:
            entree = catalog.get(slugify(clean_text(linked_title)))
            if not entree:
                continue

            canonical_technique = entree["nom"]

            technique_to_users.setdefault(canonical_technique, [])
            if canonical_character_title not in technique_to_users[canonical_technique]:
                technique_to_users[canonical_technique].append(canonical_character_title)

    return technique_to_users
