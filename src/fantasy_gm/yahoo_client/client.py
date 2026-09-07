# NOTE: Yahoo Fantasy API access is currently gated behind manual approval, so
# these parsers were validated against synthetic, spec-accurate fixtures built to
# match Yahoo's documented Fantasy v2 JSON (?format=json) shape for an NBA
# 9-category league (tests/fixtures/league_settings.json, free_agents.json).
# They must be re-verified against real Yahoo responses once API access is
# approved (see scripts/spike_oauth.py).
from typing import Any

import httpx

from fantasy_gm.schemas import LeagueSettings, Player, Team
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


def _parse_player(pdata: list) -> Player:
    meta = pdata[0]
    stats = pdata[1].get("player_stats", {}).get("stats", [])
    name = _meta(meta, "name")
    return Player(
        player_id=_meta(meta, "player_id"),
        name=name["full"] if isinstance(name, dict) else name,
        nba_team=_meta(meta, "editorial_team_abbr"),
        positions=_positions(meta),
        stats={s["stat"]["stat_id"]: float(s["stat"]["value"] or 0) for s in stats},
    )


def parse_free_agents(raw: dict[str, Any]) -> list[Player]:
    players_node = raw["fantasy_content"]["league"][1]["players"]
    return [
        _parse_player(node["player"])
        for key, node in players_node.items() if key != "count"
    ]


def parse_teams_with_rosters(raw: dict[str, Any]) -> list[Team]:
    teams_node = raw["fantasy_content"]["league"][1]["teams"]
    out: list[Team] = []
    for key, node in teams_node.items():
        if key == "count":
            continue
        tdata = node["team"]
        meta = tdata[0]
        players_node = tdata[1]["roster"]["0"]["players"]
        players = [
            _parse_player(p["player"])
            for k, p in players_node.items() if k != "count"
        ]
        out.append(Team(
            team_key=_meta(meta, "team_key"),
            name=_meta(meta, "name"),
            players=players,
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


# Live fetch wrappers (used by sync/tools; not unit-tested against the network).
# In demo mode they read local fixtures instead of calling the (approval-gated)
# Yahoo API — the bridge until real access is granted.
def _demo_mode() -> bool:
    from fantasy_gm.config import get_settings
    return get_settings().demo_mode


def fetch_league_settings(league_key: str) -> LeagueSettings:
    if _demo_mode():
        from fantasy_gm import demo
        return demo.demo_league_settings()
    return parse_league_settings(_get(f"league/{league_key}/settings"))


def fetch_free_agents(league_key: str) -> list[Player]:
    if _demo_mode():
        from fantasy_gm import demo
        return demo.demo_free_agents()
    return parse_free_agents(_get(f"league/{league_key}/players;status=FA;out=stats"))


def _wrap_team_as_league(raw: dict[str, Any]) -> dict[str, Any]:
    # TODO: validate against real Yahoo response on approval — the single-team
    # endpoint shape may differ from the league/teams shape assumed here.
    return raw


def fetch_my_team(league_key: str, team_id: str) -> Team:
    raw = _get(f"team/{league_key}.t.{team_id}/roster/players/stats")
    # team endpoint nests differently; validate/adjust against real data on approval
    return parse_teams_with_rosters(_wrap_team_as_league(raw))[0]


def fetch_all_teams(league_key: str) -> list[Team]:
    if _demo_mode():
        from fantasy_gm import demo
        return demo.demo_teams()
    return parse_teams_with_rosters(_get(f"league/{league_key}/teams;out=roster,stats"))
