"""End-to-end smoke test: build the real agent (Claude) in demo mode and ask one
question, printing each tool call and the final answer.

Prereqs in .env:
    DEMO_MODE=true
    ANTHROPIC_API_KEY=...        (real key; a live Claude call is made)
Prereqs run once:
    uv run python scripts/run_migrations.py
    uv run python scripts/seed_demo_data.py

Run:
    uv run python scripts/smoke_chat.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

from fantasy_gm.agent import build_agent  # noqa: E402
from fantasy_gm.config import get_settings  # noqa: E402
from fantasy_gm.tools import get_league_settings  # noqa: E402

LEAGUE_KEY = "428.l.123456"
MY_TEAM_KEY = "428.l.123456.t.1"

QUESTION = (
    "I'm weak in assists and steals this week. Looking at the waiver wire, who "
    "should I pick up and who should I drop? Weigh how many games each player "
    "has this week and their recent form. Give one clear recommendation."
)


def main() -> None:
    s = get_settings()
    if not s.demo_mode:
        raise SystemExit("Set DEMO_MODE=true in .env for the smoke test.")
    if not s.anthropic_api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY in .env (a live Claude call is made).")

    print(f"Model: {s.agent_model}\nQuestion: {QUESTION}\n" + "-" * 70)
    league = get_league_settings(LEAGUE_KEY)
    agent = build_agent(league=league, league_key=LEAGUE_KEY,
                        my_team_key=MY_TEAM_KEY)

    final = None
    for chunk in agent.stream({"messages": [HumanMessage(QUESTION)]},
                              stream_mode="updates"):
        for _node, update in chunk.items():
            for m in (update.get("messages", []) if isinstance(update, dict) else []):
                for tc in getattr(m, "tool_calls", None) or []:
                    print(f"  🔧 tool call: {tc['name']}({tc.get('args', {})})")
                if isinstance(m, AIMessage) and m.content:
                    final = m.content

    print("-" * 70)
    print("FINAL ANSWER:\n")
    print(final)


if __name__ == "__main__":
    main()
