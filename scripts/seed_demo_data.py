"""Seed Postgres with demo data so the Postgres-backed tools (get_weekly_schedule,
get_trends) return real values in demo mode. Run after run_migrations.py.

    uv run python scripts/seed_demo_data.py
"""
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fantasy_gm import demo  # noqa: E402
from fantasy_gm.db import execute  # noqa: E402

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo_data"


def seed_schedule() -> None:
    games = json.loads((DEMO_DIR / "schedule_week.json").read_text())
    today = date.today()
    # Seed weeks 1..25 with the same game counts so any week the agent asks for
    # returns data (the demo isn't tied to a real NBA calendar week).
    for week in range(1, 26):
        for team, total in games.items():
            execute(
                "INSERT INTO weekly_schedule "
                "(nba_team, week, games_total, games_remaining, as_of_date) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (nba_team, week) DO UPDATE SET "
                "games_total=EXCLUDED.games_total, "
                "games_remaining=EXCLUDED.games_remaining, "
                "as_of_date=EXCLUDED.as_of_date",
                (team, week, total, total, today),
            )
    print(f"seeded weekly_schedule for {len(games)} teams x 25 weeks")


def seed_snapshots() -> None:
    players = list(demo.demo_free_agents())
    for t in demo.demo_teams():
        players.extend(t.players)
    today = date.today()
    # Give recent form a per-player drift vs the season line so buy-low/sell-high
    # has real signal (some players hot, some cold). Deterministic (seeded).
    rng = random.Random(7)
    n = 0
    for p in players:
        factor = rng.uniform(0.7, 1.3)  # <1 cold (buy-low), >1 hot (sell-high)
        recent = {k: round(v * factor, 3) for k, v in p.stats.items()}
        for d in range(3):  # last 3 days -> get_trends(14d) averages them
            execute(
                "INSERT INTO player_stat_snapshots (player_id, snapshot_date, stats) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (player_id, snapshot_date) DO UPDATE SET "
                "stats=EXCLUDED.stats",
                (p.player_id, today - timedelta(days=d), json.dumps(recent)),
            )
            n += 1
    print(f"seeded {n} player_stat_snapshots for {len(players)} players")


def clear_league_config() -> None:
    # The league_config cache pins the league format (category/points). Clearing
    # it on each (re)deploy makes get_league_settings re-derive from the current
    # DEMO_LEAGUE_FORMAT env, so switching the demo format takes effect on redeploy.
    execute("DELETE FROM league_config")
    print("cleared league_config cache")


if __name__ == "__main__":
    clear_league_config()
    seed_schedule()
    seed_snapshots()
    print("demo data seeded.")
