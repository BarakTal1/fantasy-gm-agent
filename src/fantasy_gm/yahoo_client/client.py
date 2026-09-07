# NOTE: Yahoo Fantasy API access is currently gated behind manual approval, so
# these parsers were validated against synthetic, spec-accurate fixtures built to
# match Yahoo's documented Fantasy v2 JSON (?format=json) shape for an NBA
# 9-category league (tests/fixtures/league_settings.json, free_agents.json).
# They must be re-verified against real Yahoo responses once API access is
# approved (see scripts/spike_oauth.py).
from typing import Any

import httpx

from fantasy_gm.schemas import LeagueSettings, Player
from fantasy_gm.yahoo_client.auth import get_access_token

API = "https://fantasysports.yahooapis.com/fantasy/v2"


def _get(path: str) -> dict[str, Any]:
    token = get_access_token()
    r = httpx.get(f"{API}/{path}?format=json",
                  headers={"Authorization": f"Bearer {token}"}, timeout=20)
    r.raise_for_status()
    return r.json()


def parse_league_settings(raw: dict[str, Any]) -> LeagueSettings:
    league = raw["fantasy_content"]["league"]
    settings = league[1]["settings"][0]
    league_key = league[0]["league_key"]
    scoring = settings.get("scoring_type", "head")
    fmt = "points" if "point" in scoring else "category"
    categories = [
        c["stat"]["display_name"]
        for c in settings.get("stat_categories", {}).get("stats", [])
    ]
    return LeagueSettings(league_key=league_key, format=fmt, categories=categories)


def parse_free_agents(raw: dict[str, Any]) -> list[Player]:
    players_node = raw["fantasy_content"]["league"][1]["players"]
    out: list[Player] = []
    for key, node in players_node.items():
        if key == "count":
            continue
        pdata = node["player"]
        meta = pdata[0]
        stats = pdata[1].get("player_stats", {}).get("stats", [])
        out.append(Player(
            player_id=_meta(meta, "player_id"),
            name=_meta(meta, "name")["full"] if isinstance(_meta(meta, "name"), dict)
                 else _meta(meta, "name"),
            nba_team=_meta(meta, "editorial_team_abbr"),
            positions=_positions(meta),
            stats={s["stat"]["stat_id"]: float(s["stat"]["value"] or 0)
                   for s in stats},
        ))
    return out


def _meta(meta_list: list[dict], field: str):
    for item in meta_list:
        if field in item:
            return item[field]
    return ""


def _positions(meta_list: list[dict]) -> list[str]:
    val = _meta(meta_list, "eligible_positions")
    if isinstance(val, list):
        return [p.get("position", "") for p in val]
    return []


# Live fetch wrappers (used by sync/tools; not unit-tested against the network)
def fetch_league_settings(league_key: str) -> LeagueSettings:
    return parse_league_settings(_get(f"league/{league_key}/settings"))


def fetch_free_agents(league_key: str) -> list[Player]:
    return parse_free_agents(_get(f"league/{league_key}/players;status=FA;out=stats"))
