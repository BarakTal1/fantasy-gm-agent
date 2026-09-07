import json
from datetime import date, timedelta

from fantasy_gm.db import execute, fetch_all, fetch_one
from fantasy_gm.schemas import LeagueSettings, Player, Team
from fantasy_gm.yahoo_client import client


def _fetch_settings(league_key: str) -> LeagueSettings:
    return client.fetch_league_settings(league_key)


def get_league_settings(league_key: str) -> LeagueSettings:
    """Read cached config; fetch + cache only if missing (read-once behavior)."""
    row = fetch_one(
        "SELECT league_key, format, categories, roster_slots "
        "FROM league_config WHERE league_key=%s", (league_key,))
    if row is None:
        return refresh_league_settings(league_key)
    return LeagueSettings(
        league_key=row["league_key"], format=row["format"],
        categories=row["categories"], roster_slots=row["roster_slots"])


def refresh_league_settings(league_key: str) -> LeagueSettings:
    """Force a re-fetch from Yahoo and overwrite the cache."""
    s = _fetch_settings(league_key)
    execute(
        "INSERT INTO league_config (league_key, format, categories, roster_slots) "
        "VALUES (%s, %s, %s, %s) ON CONFLICT (league_key) DO UPDATE SET "
        "format=EXCLUDED.format, categories=EXCLUDED.categories, "
        "roster_slots=EXCLUDED.roster_slots, cached_at=now()",
        (s.league_key, s.format, json.dumps(s.categories),
         json.dumps(s.roster_slots)),
    )
    return s


def get_trends(player_ids: list[str], window_days: int, as_of: date) -> dict[str, dict]:
    """Mean of each stat over the trailing window, per player."""
    start = as_of - timedelta(days=window_days)
    out: dict[str, dict] = {}
    for pid in player_ids:
        rows = fetch_all(
            "SELECT stats FROM player_stat_snapshots "
            "WHERE player_id=%s AND snapshot_date > %s AND snapshot_date <= %s",
            (pid, start, as_of))
        if not rows:
            out[pid] = {}
            continue
        totals: dict[str, float] = {}
        for r in rows:
            for k, v in r["stats"].items():
                totals[k] = totals.get(k, 0.0) + float(v)
        out[pid] = {k: v / len(rows) for k, v in totals.items()}
    return out


def get_weekly_schedule(week: int) -> dict[str, dict]:
    rows = fetch_all(
        "SELECT nba_team, games_total, games_remaining FROM weekly_schedule "
        "WHERE week=%s", (week,))
    return {r["nba_team"]: {"games_total": r["games_total"],
                            "games_remaining": r["games_remaining"]} for r in rows}


def get_free_agents(league_key: str) -> list[Player]:
    return client.fetch_free_agents(league_key)


def get_all_teams(league_key: str) -> list[Team]:
    return client.fetch_all_teams(league_key)


def get_my_roster(league_key: str, my_team_key: str) -> Team:
    for t in client.fetch_all_teams(league_key):
        if t.team_key == my_team_key:
            return t
    raise ValueError(f"team {my_team_key} not found in league {league_key}")


def get_team(league_key: str, team_key: str) -> Team:
    return get_my_roster(league_key, team_key)  # same lookup, any team
