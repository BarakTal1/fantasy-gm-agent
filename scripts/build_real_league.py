"""Build a static real-NBA demo league from nba_api (run LOCALLY — stats.nba.com
blocks datacenter IPs, so we snapshot to static JSON the deployed app serves).

    uv run python scripts/build_real_league.py [SEASON]   # e.g. 2024-25
Regenerates demo_data/league.json + demo_data/free_agents.json with real players.
"""
import json
import sys
from pathlib import Path

from nba_api.stats.endpoints import leaguedashplayerstats as L

OUT = Path(__file__).resolve().parent.parent / "demo_data"
# nba_api column -> our category key
MAP = {"PTS": "PTS", "REB": "REB", "AST": "AST", "STL": "ST", "BLK": "BLK",
       "TOV": "TO", "FG3M": "3PTM", "FG_PCT": "FG%", "FT_PCT": "FT%"}
N_TEAMS, PER_TEAM = 12, 10


def _fantasy_score(s: dict) -> float:
    # rough draft-ordering value (counting cats minus turnovers)
    return (s["PTS"] + s["REB"] * 1.2 + s["AST"] * 1.5 + s["ST"] * 3
            + s["BLK"] * 3 + s["3PTM"] - s["TO"])


def build(season: str) -> None:
    df = L.LeagueDashPlayerStats(season=season, per_mode_detailed="PerGame",
                                 timeout=60).get_data_frames()[0]
    df = df[df["GP"] >= 20]  # real rotation players only
    players = []
    for _, r in df.iterrows():
        stats = {ours: round(float(r[nba]), 3) for nba, ours in MAP.items()}
        players.append({"player_id": str(int(r["PLAYER_ID"])),
                        "name": r["PLAYER_NAME"], "nba_team": r["TEAM_ABBREVIATION"],
                        "positions": [], "stats": stats})
    players.sort(key=lambda p: _fantasy_score(p["stats"]), reverse=True)

    drafted = players[: N_TEAMS * PER_TEAM]
    free_agents = players[N_TEAMS * PER_TEAM : N_TEAMS * PER_TEAM + 40]

    # snake draft into 12 teams so rosters are balanced
    teams = [[] for _ in range(N_TEAMS)]
    for i, p in enumerate(drafted):
        rnd = i // N_TEAMS
        col = i % N_TEAMS
        idx = col if rnd % 2 == 0 else (N_TEAMS - 1 - col)
        teams[idx].append(p)
    league = {"teams": [
        {"team_key": f"428.l.123456.t.{i+1}",
         "name": "My Squad" if i == 0 else f"Team {i+1}",
         "players": roster}
        for i, roster in enumerate(teams)]}

    OUT.mkdir(exist_ok=True)
    (OUT / "league.json").write_text(json.dumps(league, indent=2))
    (OUT / "free_agents.json").write_text(json.dumps({"players": free_agents}, indent=2))
    print(f"built {len(drafted)} rostered + {len(free_agents)} FAs from real {season} data")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "2024-25")
