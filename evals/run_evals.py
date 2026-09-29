"""Run the demo agent over the dataset and score it with our scorers in LangSmith.

Each example asks the agent a question and records: which tools it called, every
player name those tools returned ("known_names"), and its final answer. Two
evaluators then score that trace — grounding_score checks the answer doesn't
invent players outside known_names, tool_trajectory_score checks the agent used
the right tool lens for the question type (waiver questions must weigh the
weekly schedule, trade questions must not).

Prereqs in .env:
    DEMO_MODE=true
    ANTHROPIC_API_KEY=...   (a live Claude call is made per question)
    LANGCHAIN_API_KEY=...   (LangSmith project the results upload to)
Prereqs run once:
    uv run python scripts/run_migrations.py
    uv run python scripts/seed_demo_data.py
    uv run python evals/dataset.py

Run:
    uv run python evals/run_evals.py
"""
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402
from langsmith import evaluate  # noqa: E402
from langsmith.schemas import Example, Run  # noqa: E402

load_dotenv()

from evals.dataset import DATASET  # noqa: E402
from evals.scorers import grounding_score, tool_trajectory_score  # noqa: E402
from fantasy_gm.agent import build_agent  # noqa: E402
from fantasy_gm.config import get_settings  # noqa: E402
from fantasy_gm.tools import get_league_settings  # noqa: E402

LEAGUE_KEY = "428.l.123456"
MY_TEAM_KEY = "428.l.123456.t.1"


def _text(content) -> str:
    """Claude's content is a list of blocks (thinking + text); keep just the text."""
    if isinstance(content, str):
        return content
    return "\n".join(
        b["text"] for b in content
        if isinstance(b, dict) and b.get("type") == "text"
    )


def _collect_names(value, names: set[str]) -> None:
    """Walk a tool's JSON-shaped return value, collecting every 'name' field
    (players are the only objects in our schemas with a bare 'name' key)."""
    if isinstance(value, dict):
        name = value.get("name")
        if isinstance(name, str):
            names.add(name)
        for v in value.values():
            _collect_names(v, names)
    elif isinstance(value, list):
        for v in value:
            _collect_names(v, names)


def run_agent(question: str, agent) -> dict:
    """Drive the agent for one question, capturing the trajectory evals need."""
    tools_called: list[str] = []
    known_names: set[str] = set()
    final = ""
    for chunk in agent.stream({"messages": [HumanMessage(question)]},
                              stream_mode="updates"):
        for _node, update in chunk.items():
            for m in (update.get("messages", []) if isinstance(update, dict) else []):
                for tc in getattr(m, "tool_calls", None) or []:
                    tools_called.append(tc["name"])
                if isinstance(m, ToolMessage):
                    try:
                        _collect_names(json.loads(m.content), known_names)
                    except (json.JSONDecodeError, TypeError):
                        pass
                if isinstance(m, AIMessage) and _text(m.content):
                    final = _text(m.content)
    return {"answer": final, "tools_called": tools_called, "known_names": sorted(known_names)}


def make_target(agent):
    def target(inputs: dict) -> dict:
        return run_agent(inputs["question"], agent)
    return target


def grounding_evaluator(outputs: dict) -> dict:
    score = grounding_score(outputs["answer"], set(outputs["known_names"]))
    return {"key": "grounding", "score": score}


def tool_trajectory_evaluator(run: Run, example: Example) -> dict:
    question_type = (example.metadata or {}).get("type", "")
    tools_called = (run.outputs or {}).get("tools_called", [])
    score = tool_trajectory_score(question_type, tools_called)
    return {"key": "tool_trajectory", "score": score}


def main() -> None:
    s = get_settings()
    if not s.demo_mode:
        raise SystemExit("Set DEMO_MODE=true in .env to run evals against demo data.")
    if not s.anthropic_api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY in .env (a live Claude call is made).")
    if not os.environ.get("LANGCHAIN_API_KEY"):
        raise SystemExit("Set LANGCHAIN_API_KEY in .env to upload results to LangSmith.")

    league = get_league_settings(LEAGUE_KEY)
    agent = build_agent(league=league, league_key=LEAGUE_KEY, my_team_key=MY_TEAM_KEY)

    results = evaluate(
        make_target(agent),
        data=DATASET,
        evaluators=[grounding_evaluator, tool_trajectory_evaluator],
        experiment_prefix="fantasy-gm-agent",
    )

    scores: dict[str, list[float]] = {"grounding": [], "tool_trajectory": []}
    for row in results:
        for r in row["evaluation_results"]["results"]:
            if r.score is not None:
                scores[r.key].append(r.score)

    print(f"\nExperiment: {results.experiment_name}")
    if results.url:
        print(f"View at: {results.url}")
    for key, vals in scores.items():
        avg = sum(vals) / len(vals) if vals else 0.0
        print(f"  {key}: {avg:.2f} avg over {len(vals)} examples")


if __name__ == "__main__":
    main()
