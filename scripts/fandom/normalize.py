from __future__ import annotations

import html
import re
import unicodedata


# ------------------------------------------------------------
# Slug
# ------------------------------------------------------------

def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")

    slug = re.sub(r"[^a-z0-9\s-]", "", ascii_text.lower())
    slug = re.sub(r"\s+", "-", slug).strip("-")
    slug = re.sub(r"-+", "-", slug)

    return slug or "entity"


# ------------------------------------------------------------
# Cleaning helpers
# ------------------------------------------------------------

def normalize_infobox_value(value: str) -> str:

    if not value:
        return ""

    value = re.sub(r"<ref[^>]*>.*?</ref>", "", value, flags=re.IGNORECASE | re.DOTALL)

    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)

    value = re.sub(r"<[^>]+>", "", value)

    value = re.sub(
        r"\{\{(?:lang\|ja\|)?([^{}|]+(?:\|[^{}|]+)*)\}\}",
        lambda m: m.group(1).split("|")[-1],
        value,
    )

    value = re.sub(
        r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]",
        r"\1",
        value,
    )

    value = re.sub(
        r"\[https?://[^\s\]]+\s*([^\]]*)\]",
        r"\1",
        value,
    )

    value = re.sub(r"''+", "", value)

    value = html.unescape(value)

    value = re.sub(r"\s+", " ", value)

    return value.strip(" |")


def clean_text(value: str) -> str:

    text = normalize_infobox_value(str(value or ""))

    text = re.sub(r"\s*\(\s*\)", "", text)

    text = re.sub(r"\s*[,;]\s*$", "", text)

    return text.strip()


# ------------------------------------------------------------
# Split lists
# ------------------------------------------------------------

def split_list_field(value: str) -> list[str]:

    cleaned = clean_text(value)

    if not cleaned:
        return []

    pieces = re.split(r"(?:\n|,|;|/|\|)", cleaned)

    items: list[str] = []

    for piece in pieces:

        entry = piece.strip(" -*•")

        if not entry:
            continue

        if entry not in items:
            items.append(entry)

    return items


# ------------------------------------------------------------
# Infobox parsing
# ------------------------------------------------------------

def extract_template_block(wikitext: str) -> str:

    for template_start in re.finditer(r"\{\{\s*([^\n\|\}]+)", wikitext):

        template_name = template_start.group(1).strip().lower()

        if "infobox" not in template_name and "character" not in template_name:
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


def extract_infobox_fields(wikitext: str) -> dict[str, str]:

    infobox_text = extract_template_block(wikitext)

    if not infobox_text:
        return {}

    values: dict[str, str] = {}

    current_key: str | None = None
    buffer: list[str] = []

    def flush() -> None:

        nonlocal current_key
        nonlocal buffer

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

            current_key = key_match.group(1).lower()

            buffer = [key_match.group(2)]

            continue

        if current_key is not None:
            buffer.append(line)

    flush()

    return values


# ------------------------------------------------------------
# Intro paragraph
# ------------------------------------------------------------

# Blocs à écarter avant de chercher le texte : ils précèdent l'introduction
# dans le HTML rendu et contiennent eux aussi des <p>.
_HTML_ASIDE_BLOCKS = re.compile(
    r"<(aside|table|figure|style|script|div\s+class=\"[^\"]*(?:toc|navbox|hatnote)[^\"]*\")\b.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)

_HTML_REFERENCE_MARKS = re.compile(r"<sup\b.*?</sup>", re.IGNORECASE | re.DOTALL)

_HTML_PARAGRAPH = re.compile(r"<p\b[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)


def first_paragraph_from_html(html_text: str, minimum_length: int = 40) -> str:
    """
    Renvoie le premier vrai paragraphe d'une page rendue.

    Le wiki n'expose pas prop=extracts : on repart donc du HTML de action=parse.
    Les premiers <p> sont souvent vides ou tiennent lieu d'espacement sous
    l'infobox, d'où le seuil de longueur.
    """
    if not html_text:
        return ""

    cleaned = _HTML_ASIDE_BLOCKS.sub(" ", html_text)
    cleaned = _HTML_REFERENCE_MARKS.sub("", cleaned)

    for match in _HTML_PARAGRAPH.finditer(cleaned):
        text = re.sub(r"<[^>]+>", "", match.group(1))
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) >= minimum_length:
            return text

    return ""


# ------------------------------------------------------------
# Japanese names
# ------------------------------------------------------------

# Kana, kanji et signes d'itération/allongement.
_JAPANESE_RUN = re.compile(r"[぀-ヿ㐀-䶿一-鿿々ー]+")


def extract_japanese_name(value: str) -> str:
    """
    Isole le nom japonais d'un champ d'infobox.

    Le champ `name` mêle le nom de page et sa translittération
    ("{{PAGENAME}}<br><font size=2>タイガーショット</font>") : on ne garde que
    la plus longue suite de caractères japonais.
    """
    runs = _JAPANESE_RUN.findall(str(value or ""))

    return max(runs, key=len) if runs else ""


def strip_template_residue(value: str) -> str:
    """
    Retire les accolades fermantes qu'un champ d'infobox vide laisse traîner
    quand il termine le template.
    """
    return re.sub(r"[{}|]+\s*$", "", clean_text(value)).strip(" ,;")


# ------------------------------------------------------------
# Entity name normalization
# ------------------------------------------------------------

def normalize_entity_name(value: str) -> str:

    name = clean_text(value)

    return re.sub(r"\s+", " ", name).strip()


# ------------------------------------------------------------
# Team classification
# ------------------------------------------------------------

COMPETITION_KEYWORDS = (
    "tournament",
    "cup",
    "league",
    "championship",
)

CLUB_TEAM_KEYWORDS = (
    "fc",
    "sc",
    "sv",
    "club",
)

NATIONAL_TEAM_KEYWORDS = (
    "japan",
    "brazil",
    "germany",
    "france",
    "argentina",
)


def _contains_any_keyword(lowered_name: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in lowered_name for keyword in keywords)


def classify_team(name: str) -> dict[str, str]:

    normalized_name = normalize_entity_name(name)

    lowered_name = normalized_name.lower()

    if _contains_any_keyword(lowered_name, COMPETITION_KEYWORDS):
        return {"type": "competition", "age_category": "adult"}

    if "elementary school" in lowered_name:
        return {"type": "school", "age_category": "elementary"}

    if "middle school" in lowered_name or "junior high" in lowered_name:
        return {"type": "school", "age_category": "middle-school"}

    if "high school" in lowered_name:
        return {"type": "school", "age_category": "high-school"}

    if "olympic" in lowered_name:
        return {"type": "national", "age_category": "olympic"}

    if "jr" in lowered_name or "youth" in lowered_name:
        return {"type": "national", "age_category": "youth"}

    if _contains_any_keyword(lowered_name, CLUB_TEAM_KEYWORDS):
        return {"type": "club", "age_category": "adult"}

    if _contains_any_keyword(lowered_name, NATIONAL_TEAM_KEYWORDS):
        return {"type": "national", "age_category": "adult"}

    return {"type": "club", "age_category": "adult"}


# ------------------------------------------------------------
# Parent team grouping
# ------------------------------------------------------------

def infer_parent_team(name: str) -> str | None:

    normalized_name = normalize_entity_name(name)

    if not normalized_name:
        return None

    parent = re.sub(
        r"\s+(elementary school|middle school|high school|junior high|jr\.? youth|youth|national team)$",
        "",
        normalized_name,
        flags=re.IGNORECASE,
    ).strip()

    if not parent or parent.casefold() == normalized_name.casefold():
        return None

    return parent
