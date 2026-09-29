from datetime import date

from fantasy_gm.db import fetch_all
from fantasy_gm.schemas import Player
from fantasy_gm.sync import sync_schedule, sync_stats


def test_sync_stats_upserts_snapshot(db):
    players = [Player(player_id="1", name="X", nba_team="LAL",
                      stats={"PTS": 20.0})]
    sync_stats(players, snapshot_date=date(2026, 1, 6))
    rows = fetch_all("SELECT player_id, stats FROM player_stat_snapshots")
    assert rows[0]["player_id"] == "1"
    assert rows[0]["stats"]["PTS"] == 20.0


def test_sync_schedule_writes_counts(db):
    sync_schedule({"LAL": 4, "BOS": 3}, week=1,
                  remaining={"LAL": 4, "BOS": 3}, as_of=date(2026, 1, 6))
    rows = {r["nba_team"]: r["games_total"]
            for r in fetch_all("SELECT nba_team, games_total FROM weekly_schedule")}
    assert rows == {"LAL": 4, "BOS": 3}
