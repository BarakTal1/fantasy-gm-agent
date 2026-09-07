import json
from datetime import date

from fantasy_gm import tools
from fantasy_gm.db import execute


def test_get_league_settings_reads_cache_without_fetch(db, monkeypatch):
    execute(
        "INSERT INTO league_config (league_key, format, categories) "
        "VALUES (%s, %s, %s)",
        ("428.l.1", "category", json.dumps(["PTS", "AST"])),
    )
    # If it tries to fetch from Yahoo, fail the test.
    monkeypatch.setattr(tools, "_fetch_settings",
                        lambda k: (_ for _ in ()).throw(AssertionError("fetched!")))
    s = tools.get_league_settings("428.l.1")
    assert s.categories == ["PTS", "AST"]


def test_get_trends_averages_recent_snapshots(db):
    execute("INSERT INTO player_stat_snapshots VALUES (%s,%s,%s)",
            ("1", date(2026, 1, 5), json.dumps({"PTS": 10.0})))
    execute("INSERT INTO player_stat_snapshots VALUES (%s,%s,%s)",
            ("1", date(2026, 1, 6), json.dumps({"PTS": 30.0})))
    trend = tools.get_trends(["1"], window_days=14,
                             as_of=date(2026, 1, 7))
    assert trend["1"]["PTS"] == 20.0  # mean of 10 and 30


def test_get_weekly_schedule_reads_table(db):
    execute("INSERT INTO weekly_schedule VALUES (%s,%s,%s,%s,%s)",
            ("LAL", 1, 4, 3, date(2026, 1, 6)))
    sched = tools.get_weekly_schedule(week=1)
    assert sched["LAL"]["games_remaining"] == 3
