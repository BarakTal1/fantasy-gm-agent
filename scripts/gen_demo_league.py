"""Generate a realistic 12-team demo league into demo_data/. Deterministic (seeded).
Run: uv run python scripts/gen_demo_league.py"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

CATS = ["PTS", "REB", "AST", "ST", "BLK", "3PTM", "FG%", "FT%", "TO"]
NBA = ["LAL", "BOS", "DEN", "MIL", "PHX", "GSW", "MIN", "NYK", "OKC", "IND",
       "MIA", "DAL", "SAC", "PHI", "CLE", "NOP"]
FIRST = ["Jalen", "Marcus", "Andre", "Tyrus", "Devin", "Cody", "Malik", "Zion",
         "Trey", "Isaiah", "Jaylen", "Darius", "Cam", "Keon", "Brandon", "Xavier",
         "Amari", "Kobe", "Elijah", "Nate"]
LAST = ["Reed", "Vance", "Cole", "Bell", "Park", "Ford", "Hayes", "Blake", "Diaz",
        "Grant", "Moss", "Poole", "Rowe", "Sharp", "Tate", "Ware", "Young", "Booker",
        "Ellis", "Frazier"]


def _player(rng, pid):
    return {
        "player_id": str(pid),
        "name": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
        "nba_team": rng.choice(NBA),
        "positions": [rng.choice(["PG", "SG", "SF", "PF", "C"])],
        "stats": {
            "PTS": round(rng.uniform(6, 28), 1), "REB": round(rng.uniform(2, 12), 1),
            "AST": round(rng.uniform(1, 9), 1), "ST": round(rng.uniform(0.4, 2.0), 1),
            "BLK": round(rng.uniform(0.2, 2.2), 1), "3PTM": round(rng.uniform(0.4, 3.6), 1),
            "FG%": round(rng.uniform(0.41, 0.55), 3), "FT%": round(rng.uniform(0.65, 0.9), 3),
            "TO": round(rng.uniform(0.7, 3.2), 1),
        },
    }


if __name__ == "__main__":
    rng = random.Random(42)
    pid = 1000
    teams = []
    for t in range(1, 13):
        players = [_player(rng, (pid := pid + 1)) for _ in range(10)]
        teams.append({"team_key": f"428.l.123456.t.{t}",
                      "name": "My Squad" if t == 1 else f"Team {t}",
                      "players": players})
    free_agents = [_player(rng, (pid := pid + 1)) for _ in range(30)]
    out = Path("demo_data")
    out.mkdir(exist_ok=True)
    (out / "league.json").write_text(json.dumps({"teams": teams}, indent=2))
    (out / "free_agents.json").write_text(json.dumps({"players": free_agents}, indent=2))
    print(f"generated {len(teams)} teams and {len(free_agents)} free agents")
