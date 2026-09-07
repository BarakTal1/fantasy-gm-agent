import json
from datetime import date

from fantasy_gm.db import execute
from fantasy_gm.schemas import Player


def sync_stats(players: list[Player], snapshot_date: date) -> None:
    for p in players:
        execute(
            "INSERT INTO player_stat_snapshots (player_id, snapshot_date, stats) "
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (player_id, snapshot_date) DO UPDATE SET stats=EXCLUDED.stats",
            (p.player_id, snapshot_date, json.dumps(p.stats)),
        )


def sync_schedule(games_total: dict[str, int], week: int,
                  remaining: dict[str, int], as_of: date) -> None:
    for team, total in games_total.items():
        execute(
            "INSERT INTO weekly_schedule "
            "(nba_team, week, games_total, games_remaining, as_of_date) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (nba_team, week) DO UPDATE SET "
            "games_total=EXCLUDED.games_total, "
            "games_remaining=EXCLUDED.games_remaining, "
            "as_of_date=EXCLUDED.as_of_date",
            (team, week, total, remaining.get(team, total), as_of),
        )
