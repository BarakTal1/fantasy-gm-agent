"""Demo-mode data provider.

Reads the committed demo fixtures (demo_data/) and returns clean schema objects,
so the whole agent can run end-to-end before Yahoo API access is approved.
Stat keys are remapped from Yahoo stat_ids to human category names (PTS, AST, ...)
using the league settings, so the LLM sees readable stats.
"""
import json
from pathlib import Path

from fantasy_gm.schemas import LeagueSettings, Player, Team
from fantasy_gm.yahoo_client import client

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo_data"


def _load(name: str) -> dict:
    return json.loads((DEMO_DIR / name).read_text())


def _stat_id_to_name() -> dict[str, str]:
    stats = (_load("league_settings.json")["fantasy_content"]["league"][1]
             ["settings"][0]["stat_categories"]["stats"])
    return {str(s["stat"]["stat_id"]): s["stat"]["display_name"] for s in stats}


def _rename(players: list[Player], mapping: dict[str, str]) -> list[Player]:
    for p in players:
        p.stats = {mapping.get(k, k): v for k, v in p.stats.items()}
    return players


def demo_league_settings() -> LeagueSettings:
    return client.parse_league_settings(_load("league_settings.json"))


def demo_free_agents() -> list[Player]:
    return _rename(client.parse_free_agents(_load("free_agents.json")),
                   _stat_id_to_name())


def demo_teams() -> list[Team]:
    mapping = _stat_id_to_name()
    teams = client.parse_teams_with_rosters(_load("roster.json"))
    for t in teams:
        _rename(t.players, mapping)
    return teams
