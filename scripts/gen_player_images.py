"""Generate demo_data/player_images.json from the demo roster + free agents.

Maps every demo player_id to its official NBA CDN headshot URL. Re-run if the
demo league is regenerated: `uv run python scripts/gen_player_images.py`.
"""
import json
from pathlib import Path

DEMO = Path(__file__).resolve().parent.parent / "demo_data"
CDN = "https://cdn.nba.com/headshots/nba/latest/260x190/{id}.png"


def main() -> None:
    ids: set[str] = set()
    league = json.loads((DEMO / "league.json").read_text())
    for team in league["teams"]:
        for p in team["players"]:
            ids.add(p["player_id"])
    fas = json.loads((DEMO / "free_agents.json").read_text())
    for p in fas["players"]:
        ids.add(p["player_id"])
    table = {pid: CDN.format(id=pid) for pid in sorted(ids)}
    (DEMO / "player_images.json").write_text(json.dumps(table, indent=2) + "\n")
    print(f"wrote {len(table)} entries to demo_data/player_images.json")


if __name__ == "__main__":
    main()
