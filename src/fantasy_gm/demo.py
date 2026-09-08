"""Demo-mode data provider.

Reads the committed demo fixtures (demo_data/) and returns clean schema objects,
so the whole agent can run end-to-end before Yahoo API access is approved.
Team/free-agent data is read from the generated simple-schema files
(demo_data/league.json, demo_data/free_agents.json) whose stat keys are already
human category names (PTS, AST, ...). League settings still come from the
Yahoo-shaped league_settings.json fixture.
"""
import json
from pathlib import Path

from fantasy_gm.schemas import LeagueSettings, Player, Team
from fantasy_gm.yahoo_client import client

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo_data"


def _load(name: str) -> dict:
    return json.loads((DEMO_DIR / name).read_text())


def demo_league_settings() -> LeagueSettings:
    return client.parse_league_settings(_load("league_settings.json"))


def _player(d: dict) -> Player:
    return Player(player_id=d["player_id"], name=d["name"], nba_team=d["nba_team"],
                  positions=d.get("positions", []), stats=d["stats"])


def demo_teams() -> list[Team]:
    data = _load("league.json")
    return [Team(team_key=t["team_key"], name=t["name"],
                 players=[_player(p) for p in t["players"]]) for t in data["teams"]]


def demo_free_agents() -> list[Player]:
    return [_player(p) for p in _load("free_agents.json")["players"]]
