from __future__ import annotations

from .normalize import normalize_entity_name, split_list_field

TEAM_INFOBOX_FIELDS = (
    "team",
    "former_team",
    "club",
    "current_team",
    "national_team",
    "youth_team",
    "team_name",
)


def extract_teams_from_infobox(infobox: dict[str, str]) -> list[str]:
    teams: list[str] = []
    for field in TEAM_INFOBOX_FIELDS:
        raw_value = infobox.get(field, "")
        for candidate in split_list_field(raw_value):
            normalized = normalize_entity_name(candidate)
            if not normalized:
                continue
            if normalized not in teams:
                teams.append(normalized)
    return teams
