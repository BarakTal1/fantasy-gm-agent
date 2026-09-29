# Phase 2 — Agent, API & Evals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Phase 1 data foundation into a working conversational agent: wrap the toolbox as LangGraph tools, build a LangGraph/Claude agent with league-config seeding and guardrails, expose it over a streaming FastAPI `/chat` endpoint with Postgres-backed memory, and add a LangSmith pre-ship eval harness (grounding + tool-trajectory scorers).

**Architecture:** A `ChatAnthropic` (Claude) model drives a LangGraph `create_react_agent` loop bound to the toolbox from `tools.py` (exposed as LangChain tools in `agent_tools.py`). The agent is constructed by a `build_agent()` factory (`agent.py`) that seeds the system prompt with the cached league config and attaches a Postgres checkpointer for per-conversation memory. FastAPI (`api.py`) streams the agent's tool events and answer tokens over SSE. A grounding checker (`guardrails.py`) and LangSmith scorers (`evals/`) form the quality gate. Determinism boundary: everything except the LLM's own decisions is unit-tested; the LLM's judgment is validated by LangSmith evals, not unit tests. Agent-loop *wiring* is unit-tested with a scripted fake chat model.

**Tech Stack:** Phase 1 stack + `langgraph`, `langchain-core`, `langchain-anthropic` (Claude via `ChatAnthropic`), `langsmith`, FastAPI + `uvicorn`, `httpx` (already present) for the API test client.

**⚠️ API-drift note (read before Task 1):** LangGraph and LangChain APIs move fast, and Claude model behavior differs by model. This plan targets the current documented surface (`langgraph.prebuilt.create_react_agent`, `langchain_anthropic.ChatAnthropic`, `langgraph.checkpoint.postgres.PostgresSaver`). **Task 0 pins exact versions and smoke-tests every import/signature this plan uses** — if a signature has drifted (e.g. `create_react_agent`'s `prompt` vs `state_modifier` kwarg), adjust the later tasks to match what Task 0's smoke test proves, and note the change.

---

## File Structure

```
src/fantasy_gm/agent_tools.py    # toolbox functions wrapped as LangChain @tool objects
src/fantasy_gm/agent.py          # build_agent() factory: model + tools + prompt + checkpointer
src/fantasy_gm/guardrails.py     # grounding checker (no invented players)
src/fantasy_gm/api.py            # FastAPI app: POST /chat (SSE stream), GET /health
src/fantasy_gm/prompts.py        # system prompt builder (seeds league config + rules)
evals/dataset.py                 # build/seed the LangSmith eval dataset
evals/scorers.py                 # grounding + tool-trajectory scorers (pure functions)
evals/run_evals.py               # run the agent over the dataset in LangSmith
tests/test_agent_tools.py
tests/test_agent.py              # uses a scripted fake chat model
tests/test_guardrails.py
tests/test_api.py                # FastAPI TestClient + fake model
tests/test_scorers.py
tests/fixtures/roster.json       # spec-accurate roster fixture (added in Task 2)
tests/support/fake_chat.py       # scripted fake ChatModel for deterministic agent tests
```

Also modifies: `src/fantasy_gm/config.py` (add `agent_model`), `src/fantasy_gm/yahoo_client/client.py` (add roster/team/stats parsers), `src/fantasy_gm/tools.py` (add roster/team/free-agent/stats tools), `pyproject.toml`, `README.md`.

---

## Task 0: Dependencies & import smoke test

**Files:** Modify `pyproject.toml`; Create `scripts/smoke_langgraph.py`

- [ ] **Step 1: Add dependencies**

```bash
uv add langgraph langchain-core langchain-anthropic langsmith fastapi uvicorn
uv add --dev pytest-asyncio
```

- [ ] **Step 2: Write `scripts/smoke_langgraph.py`** to prove the exact import surface this plan relies on

```python
"""Verify the LangGraph/LangChain/Anthropic import surface this plan uses.
Run once after installing deps. If anything here fails, the API has drifted;
adjust the plan's later tasks to match what actually imports."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import inspect

from langchain_anthropic import ChatAnthropic  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from langgraph.checkpoint.postgres import PostgresSaver  # noqa: E402
from langgraph.prebuilt import create_react_agent  # noqa: E402

sig = inspect.signature(create_react_agent)
print("create_react_agent params:", list(sig.parameters))
print("ChatAnthropic ok:", ChatAnthropic.__name__)
print("messages ok:", AIMessage.__name__, HumanMessage.__name__, ToolMessage.__name__)
print("tool decorator ok:", tool.__name__)
print("PostgresSaver ok:", PostgresSaver.__name__)
print("SMOKE OK")
```

- [ ] **Step 3: Run it**

```bash
uv run python scripts/smoke_langgraph.py
```
Expected: prints `SMOKE OK` and the real `create_react_agent` parameter list. **Note whether the system-prompt kwarg is `prompt` or `state_modifier`** — the plan uses `prompt=`; if the smoke test shows only `state_modifier`, use that in Task 5 instead.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock scripts/smoke_langgraph.py
git commit -m "chore: add agent/API deps and import smoke test"
```

---

## Task 1: Config — agent model setting

**Files:** Modify `src/fantasy_gm/config.py`; Test `tests/test_config.py` (add a case)

- [ ] **Step 1: Add the failing test** (append to `tests/test_config.py`)

```python
def test_agent_model_default():
    from fantasy_gm.config import Settings
    assert Settings(_env_file=None).agent_model == "claude-opus-5"
```

- [ ] **Step 2: Run it, confirm fail**

Run: `uv run pytest tests/test_config.py::test_agent_model_default -v`
Expected: FAIL (`AttributeError: agent_model`).

- [ ] **Step 3: Add the field** to `Settings` in `config.py` (next to `anthropic_api_key`)

```python
    # Claude model for the agent. Default is the most capable; override via env
    # AGENT_MODEL=claude-sonnet-5 for a cheaper/faster option.
    agent_model: str = "claude-opus-5"
```

- [ ] **Step 4: Run it, confirm pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/config.py tests/test_config.py
git commit -m "feat: configurable agent model (default claude-opus-5)"
```

---

## Task 2: Roster/team/stats parsers + fixture

**Files:** Create `tests/fixtures/roster.json`; Modify `src/fantasy_gm/yahoo_client/client.py`; Test `tests/test_client.py` (add cases)

- [ ] **Step 1: Create the spec-accurate `tests/fixtures/roster.json`** (one team with two players; same shape family as `free_agents.json`)

```json
{
  "fantasy_content": {
    "league": [
      {"league_key": "428.l.123456"},
      {
        "teams": {
          "0": {
            "team": [
              [
                {"team_key": "428.l.123456.t.1"},
                {"team_id": "1"},
                {"name": "My Squad"}
              ],
              {
                "roster": {
                  "0": {
                    "players": {
                      "0": {
                        "player": [
                          [
                            {"player_key": "428.p.4001"},
                            {"player_id": "4001"},
                            {"name": {"full": "Tyrese Haliburton"}},
                            {"editorial_team_abbr": "IND"},
                            {"eligible_positions": [{"position": "PG"}]}
                          ],
                          {"player_stats": {"stats": [
                            {"stat": {"stat_id": "12", "value": "18.6"}},
                            {"stat": {"stat_id": "16", "value": "9.2"}}
                          ]}}
                        ]
                      },
                      "1": {
                        "player": [
                          [
                            {"player_key": "428.p.4002"},
                            {"player_id": "4002"},
                            {"name": {"full": "Myles Turner"}},
                            {"editorial_team_abbr": "IND"},
                            {"eligible_positions": [{"position": "C"}]}
                          ],
                          {"player_stats": {"stats": [
                            {"stat": {"stat_id": "12", "value": "15.9"}},
                            {"stat": {"stat_id": "18", "value": "1.9"}}
                          ]}}
                        ]
                      },
                      "count": 2
                    }
                  }
                }
              }
            ]
          },
          "count": 1
        }
      }
    ]
  }
}
```

- [ ] **Step 2: Add the failing test** (append to `tests/test_client.py`)

```python
from fantasy_gm.yahoo_client.client import parse_teams_with_rosters


def test_parse_teams_with_rosters(fixture):
    teams = parse_teams_with_rosters(fixture("roster.json"))
    assert len(teams) == 1
    t = teams[0]
    assert t.name == "My Squad"
    assert {p.name for p in t.players} == {"Tyrese Haliburton", "Myles Turner"}
    hali = next(p for p in t.players if p.name == "Tyrese Haliburton")
    assert hali.stats["16"] == 9.2  # assists
```

- [ ] **Step 3: Run it, confirm fail**

Run: `uv run pytest tests/test_client.py::test_parse_teams_with_rosters -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 4: Implement `parse_teams_with_rosters` + a shared player parser** in `client.py`

Refactor the player-parsing out of `parse_free_agents` into a reusable helper, then add the teams parser:

```python
from fantasy_gm.schemas import Team  # add to existing imports


def _parse_player(pdata: list) -> Player:
    meta = pdata[0]
    stats = pdata[1].get("player_stats", {}).get("stats", [])
    name = _meta(meta, "name")
    return Player(
        player_id=_meta(meta, "player_id"),
        name=name["full"] if isinstance(name, dict) else name,
        nba_team=_meta(meta, "editorial_team_abbr"),
        positions=_positions(meta),
        stats={s["stat"]["stat_id"]: float(s["stat"]["value"] or 0) for s in stats},
    )


def parse_teams_with_rosters(raw: dict[str, Any]) -> list[Team]:
    teams_node = raw["fantasy_content"]["league"][1]["teams"]
    out: list[Team] = []
    for key, node in teams_node.items():
        if key == "count":
            continue
        tdata = node["team"]
        meta = tdata[0]
        players_node = tdata[1]["roster"]["0"]["players"]
        players = [
            _parse_player(p["player"])
            for k, p in players_node.items() if k != "count"
        ]
        out.append(Team(
            team_key=_meta(meta, "team_key"),
            name=_meta(meta, "name"),
            players=players,
        ))
    return out
```

Then simplify `parse_free_agents` to reuse `_parse_player`:

```python
def parse_free_agents(raw: dict[str, Any]) -> list[Player]:
    players_node = raw["fantasy_content"]["league"][1]["players"]
    return [
        _parse_player(node["player"])
        for key, node in players_node.items() if key != "count"
    ]
```

- [ ] **Step 5: Run tests, confirm pass** (both the new test and the existing `parse_free_agents` test must still pass)

Run: `uv run pytest tests/test_client.py -v`
Expected: PASS.

- [ ] **Step 6: Add live-fetch wrappers** at the bottom of `client.py`

```python
def fetch_my_team(league_key: str, team_id: str) -> Team:
    raw = _get(f"team/{league_key}.t.{team_id}/roster/players/stats")
    # team endpoint nests differently; validate/adjust against real data on approval
    return parse_teams_with_rosters(_wrap_team_as_league(raw))


def fetch_all_teams(league_key: str) -> list[Team]:
    return parse_teams_with_rosters(_get(f"league/{league_key}/teams;out=roster,stats"))
```

Note: `fetch_my_team`'s single-team endpoint shape differs from the league/teams shape; leave `_wrap_team_as_league` as a thin adapter stub with a `# TODO: validate against real Yahoo response on approval` comment — it is only exercised live, never in unit tests. For Phase 2, `fetch_all_teams` + filtering by team is sufficient; prefer it.

- [ ] **Step 7: Commit**

```bash
git add src/fantasy_gm/yahoo_client/client.py tests/test_client.py tests/fixtures/roster.json
git commit -m "feat: parse teams/rosters; reuse shared player parser"
```

---

## Task 3: Toolbox — roster/free-agent/stats functions

**Files:** Modify `src/fantasy_gm/tools.py`; Test `tests/test_tools.py` (add cases)

- [ ] **Step 1: Add the failing test** (append to `tests/test_tools.py`)

```python
def test_get_free_agents_delegates_to_client(monkeypatch):
    from fantasy_gm import tools
    from fantasy_gm.schemas import Player
    sentinel = [Player(player_id="1", name="X", nba_team="LAL")]
    monkeypatch.setattr(tools.client, "fetch_free_agents", lambda k: sentinel)
    assert tools.get_free_agents("428.l.1") == sentinel


def test_get_my_roster_filters_team(monkeypatch):
    from fantasy_gm import tools
    from fantasy_gm.schemas import Player, Team
    teams = [
        Team(team_key="428.l.1.t.1", name="Mine",
             players=[Player(player_id="1", name="A", nba_team="IND")]),
        Team(team_key="428.l.1.t.2", name="Theirs",
             players=[Player(player_id="2", name="B", nba_team="BOS")]),
    ]
    monkeypatch.setattr(tools.client, "fetch_all_teams", lambda k: teams)
    mine = tools.get_my_roster("428.l.1", "428.l.1.t.1")
    assert mine.name == "Mine"
```

- [ ] **Step 2: Run it, confirm fail**

Run: `uv run pytest tests/test_tools.py -k "delegates or filters" -v`
Expected: FAIL (`AttributeError`).

- [ ] **Step 3: Implement** in `tools.py`

```python
from fantasy_gm.schemas import Player, Team  # extend existing import


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
```

- [ ] **Step 4: Run tests, confirm pass**

Run: `uv run pytest tests/test_tools.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/tools.py tests/test_tools.py
git commit -m "feat: roster/team/free-agent toolbox functions"
```

---

## Task 4: LangChain tool wrappers

**Files:** Create `src/fantasy_gm/agent_tools.py`; Test `tests/test_agent_tools.py`

These wrap the plain `tools.py` functions as LangChain `@tool` objects with clear descriptions the LLM reads to decide when to call them. The league key and my-team key are bound at agent-build time (closure), so the LLM only supplies query-specific args.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent_tools.py
from datetime import date

from fantasy_gm import agent_tools


def test_build_tools_returns_named_langchain_tools(monkeypatch):
    from fantasy_gm import tools
    monkeypatch.setattr(tools, "get_weekly_schedule",
                        lambda week: {"LAL": {"games_total": 4, "games_remaining": 3}})
    lc_tools = agent_tools.build_tools(league_key="428.l.1", my_team_key="428.l.1.t.1")
    names = {t.name for t in lc_tools}
    assert {"get_weekly_schedule", "get_free_agents", "get_my_roster",
            "get_trends"}.issubset(names)
    # tools are invocable and carry a description the LLM can read
    sched = next(t for t in lc_tools if t.name == "get_weekly_schedule")
    assert sched.description
    assert sched.invoke({"week": 15}) == {"LAL": {"games_total": 4, "games_remaining": 3}}
```

- [ ] **Step 2: Run it, confirm fail**

Run: `uv run pytest tests/test_agent_tools.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `src/fantasy_gm/agent_tools.py`**

```python
from datetime import date, timedelta

from langchain_core.tools import StructuredTool

from fantasy_gm import tools


def build_tools(league_key: str, my_team_key: str) -> list:
    """Wrap the toolbox as LangChain tools, binding league/team context."""

    def get_my_roster() -> dict:
        """Get the user's current team roster and each player's stats."""
        return tools.get_my_roster(league_key, my_team_key).model_dump()

    def get_free_agents() -> list[dict]:
        """List available free-agent/waiver players with their stats."""
        return [p.model_dump() for p in tools.get_free_agents(league_key)]

    def get_league_settings() -> dict:
        """Get the league's scoring format, categories, and roster slots."""
        return tools.get_league_settings(league_key).model_dump()

    def get_trends(player_ids: list[str], window_days: int = 14) -> dict:
        """Recent per-game form (mean of each stat) over the trailing window,
        per player id. Use for buy-low/sell-high and short-term decisions."""
        return tools.get_trends(player_ids, window_days, date.today())

    def get_weekly_schedule(week: int) -> dict:
        """How many games each NBA team plays this week and how many remain.
        Use for waiver/streaming/start-sit value, NOT for long-term trade value."""
        return tools.get_weekly_schedule(week)

    return [
        StructuredTool.from_function(get_my_roster),
        StructuredTool.from_function(get_free_agents),
        StructuredTool.from_function(get_league_settings),
        StructuredTool.from_function(get_trends),
        StructuredTool.from_function(get_weekly_schedule),
    ]
```

- [ ] **Step 4: Run it, confirm pass**

Run: `uv run pytest tests/test_agent_tools.py -v`
Expected: PASS. (If `StructuredTool.from_function` uses a different name derivation, adjust the assertion or pass `name=` explicitly — verify against Task 0's smoke output.)

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/agent_tools.py tests/test_agent_tools.py
git commit -m "feat: LangChain tool wrappers binding league context"
```

---

## Task 5: The agent + system prompt

**Files:** Create `src/fantasy_gm/prompts.py`, `src/fantasy_gm/agent.py`, `tests/support/fake_chat.py`, `tests/support/__init__.py`; Test `tests/test_agent.py`

- [ ] **Step 1: Write the system-prompt builder** `src/fantasy_gm/prompts.py`

```python
from fantasy_gm.schemas import LeagueSettings

RULES = """You are an expert NBA fantasy basketball assistant.

Rules you must follow:
- Only cite players and stats returned by your tools. Never invent a player,
  team, or number. If a tool gives you nothing, say so plainly.
- For waiver/streaming/start-sit questions, weigh how many games a player has
  THIS WEEK (call get_weekly_schedule) times recent form (get_trends).
- For evaluating trades of core players, use season-long value; ignore this
  week's schedule as noise.
- You recommend only. You never execute roster moves.
- End with a short, concrete recommendation and a one-line justification.
"""


def build_system_prompt(settings: LeagueSettings) -> str:
    fmt = "category" if settings.is_category else "points"
    cats = ", ".join(settings.categories) if settings.categories else "n/a"
    return (
        f"{RULES}\nThis league is {fmt}-scored. "
        f"Scoring categories: {cats}. "
        f"Adapt all reasoning to this format."
    )
```

- [ ] **Step 2: Write the scripted fake chat model** `tests/support/fake_chat.py` (lets us test the loop wiring deterministically, no API calls)

```python
"""A minimal scripted chat model for deterministic agent tests.
It replays a fixed list of AIMessages; if a message has tool_calls, the agent
runs the tool and calls the model again, advancing to the next scripted message.
"""
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class FakeToolCallingModel(BaseChatModel):
    responses: list[AIMessage]
    i: int = 0

    @property
    def _llm_type(self) -> str:
        return "fake-tool-calling"

    def _generate(self, messages: list[BaseMessage], stop=None,
                  run_manager: CallbackManagerForLLMRun | None = None,
                  **kwargs: Any) -> ChatResult:
        msg = self.responses[min(self.i, len(self.responses) - 1)]
        self.i += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def bind_tools(self, tools, **kwargs):  # create_react_agent calls this
        return self
```

- [ ] **Step 3: Write the failing agent test** `tests/test_agent.py`

```python
from langchain_core.messages import AIMessage, HumanMessage

from fantasy_gm.agent import build_agent
from fantasy_gm.schemas import LeagueSettings
from tests.support.fake_chat import FakeToolCallingModel


def _league():
    return LeagueSettings(league_key="428.l.1", format="category",
                          categories=["PTS", "AST"])


def test_agent_calls_tool_then_answers():
    # Script: first turn asks for the weekly schedule tool, second turn answers.
    scripted = FakeToolCallingModel(responses=[
        AIMessage(content="", tool_calls=[{
            "name": "get_weekly_schedule", "args": {"week": 15}, "id": "call_1"}]),
        AIMessage(content="Pick up players with 4 games this week."),
    ])
    agent = build_agent(
        league=_league(), league_key="428.l.1", my_team_key="428.l.1.t.1",
        model=scripted, checkpointer=None,
    )
    import fantasy_gm.tools as tools_mod
    # stub the underlying tool so no DB is needed
    tools_mod.get_weekly_schedule = lambda week: {"LAL": {"games_total": 4,
                                                          "games_remaining": 4}}
    result = agent.invoke({"messages": [HumanMessage("Who should I pick up?")]})
    final = result["messages"][-1]
    assert "4 games" in final.content
```

- [ ] **Step 4: Run it, confirm fail**

Run: `uv run pytest tests/test_agent.py -v`
Expected: FAIL (`ModuleNotFoundError: fantasy_gm.agent`).

- [ ] **Step 5: Implement `src/fantasy_gm/agent.py`**

```python
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from fantasy_gm.agent_tools import build_tools
from fantasy_gm.config import get_settings
from fantasy_gm.prompts import build_system_prompt
from fantasy_gm.schemas import LeagueSettings


def build_agent(league: LeagueSettings, league_key: str, my_team_key: str,
                model=None, checkpointer=None):
    """Construct the LangGraph agent. Pass `model` in tests (a fake); in
    production it defaults to ChatAnthropic on the configured Claude model."""
    if model is None:
        model = ChatAnthropic(
            model=get_settings().agent_model, max_tokens=4096)
    lc_tools = build_tools(league_key=league_key, my_team_key=my_team_key)
    return create_react_agent(
        model,
        lc_tools,
        prompt=build_system_prompt(league),   # if Task 0 showed state_modifier, use that
        checkpointer=checkpointer,
    )
```

- [ ] **Step 6: Run it, confirm pass**

Run: `uv run pytest tests/test_agent.py -v`
Expected: PASS. If `create_react_agent` rejects `prompt=`, switch to the kwarg Task 0's smoke test reported (e.g. `state_modifier=`).

- [ ] **Step 7: Commit**

```bash
git add src/fantasy_gm/prompts.py src/fantasy_gm/agent.py tests/support/ tests/test_agent.py
git commit -m "feat: LangGraph/Claude agent with league-seeded prompt"
```

---

## Task 6: Grounding guardrail

**Files:** Create `src/fantasy_gm/guardrails.py`; Test `tests/test_guardrails.py`

A post-hoc check used by the eval scorer (Task 9) and available for runtime logging: given the final answer text and the player names the tools actually returned, flag any player-like name in the answer that wasn't in the tool data.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guardrails.py
from fantasy_gm.guardrails import ungrounded_players


def test_flags_player_not_in_tool_data():
    answer = "Pick up Josh Hart and drop LeBron James."
    known = {"Josh Hart", "Alex Caruso"}
    assert ungrounded_players(answer, known) == ["LeBron James"]


def test_no_flags_when_all_grounded():
    answer = "Pick up Josh Hart over Alex Caruso."
    known = {"Josh Hart", "Alex Caruso"}
    assert ungrounded_players(answer, known) == []
```

- [ ] **Step 2: Run it, confirm fail**

Run: `uv run pytest tests/test_guardrails.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `src/fantasy_gm/guardrails.py`**

```python
import re

# Matches "Firstname Lastname" style capitalized bigrams (NBA player names).
_NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)\b")


def ungrounded_players(answer: str, known_names: set[str]) -> list[str]:
    """Capitalized full-name mentions in `answer` that are not in `known_names`.
    known_names = every player name returned by tools this turn."""
    found = _NAME_RE.findall(answer)
    seen: list[str] = []
    for name in found:
        if name not in known_names and name not in seen:
            seen.append(name)
    return seen
```

- [ ] **Step 4: Run it, confirm pass**

Run: `uv run pytest tests/test_guardrails.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/guardrails.py tests/test_guardrails.py
git commit -m "feat: grounding guardrail — detect ungrounded player mentions"
```

---

## Task 7: FastAPI `/chat` with SSE streaming

**Files:** Create `src/fantasy_gm/api.py`; Test `tests/test_api.py`

Streams two kinds of Server-Sent Events: `tool` (a tool started) and `token`/`final` (the answer). Uses LangGraph's `.stream(..., stream_mode="updates")` to surface tool + model steps. The league config is loaded once per request from the toolbox (cached in Postgres).

- [ ] **Step 1: Write the failing test** (uses a fake model; monkeypatches agent construction so no API/DB)

```python
# tests/test_api.py
import json

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage


def test_chat_streams_final_answer(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import LeagueSettings
    from tests.support.fake_chat import FakeToolCallingModel

    monkeypatch.setattr(api, "_load_league",
                        lambda: LeagueSettings(league_key="428.l.1",
                                               format="category", categories=["PTS"]))
    monkeypatch.setattr(api, "_make_model",
                        lambda: FakeToolCallingModel(responses=[
                            AIMessage(content="Start your 4-game players.")]))

    client = TestClient(api.app)
    with client.stream("POST", "/chat",
                       json={"message": "who do I start?",
                             "conversation_id": "c1"}) as r:
        assert r.status_code == 200
        body = "".join(chunk for chunk in r.iter_text())
    assert "Start your 4-game players." in body


def test_health():
    from fantasy_gm import api
    assert TestClient(api.app).get("/health").json() == {"status": "ok"}
```

- [ ] **Step 2: Run it, confirm fail**

Run: `uv run pytest tests/test_api.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `src/fantasy_gm/api.py`**

```python
import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from fantasy_gm.agent import build_agent
from fantasy_gm.config import get_settings
from fantasy_gm.schemas import LeagueSettings
from fantasy_gm.tools import get_league_settings

app = FastAPI(title="Fantasy GM Agent")

# Single-user demo config — replace with real values / auth in a multi-user build.
LEAGUE_KEY = "428.l.123456"
MY_TEAM_KEY = "428.l.123456.t.1"


class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"


def _load_league() -> LeagueSettings:
    return get_league_settings(LEAGUE_KEY)


def _make_model():
    return ChatAnthropic(model=get_settings().agent_model, max_tokens=4096)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    agent = build_agent(league=_load_league(), league_key=LEAGUE_KEY,
                        my_team_key=MY_TEAM_KEY, model=_make_model())

    def gen():
        for chunk in agent.stream(
            {"messages": [HumanMessage(req.message)]},
            stream_mode="updates",
        ):
            for node, update in chunk.items():
                msgs = update.get("messages", []) if isinstance(update, dict) else []
                for m in msgs:
                    tool_calls = getattr(m, "tool_calls", None)
                    if tool_calls:
                        for tc in tool_calls:
                            yield _sse("tool", {"name": tc["name"]})
                    elif isinstance(m, AIMessage) and m.content:
                        yield _sse("final", {"text": m.content})

    return StreamingResponse(gen(), media_type="text/event-stream")
```

- [ ] **Step 4: Run it, confirm pass**

Run: `uv run pytest tests/test_api.py -v`
Expected: PASS. (Adjust the `.stream` chunk-shape handling if Task 0's LangGraph version returns a different update structure — the test will show it.)

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/api.py tests/test_api.py
git commit -m "feat: FastAPI /chat with SSE tool+answer streaming"
```

---

## Task 8: Postgres-backed conversation memory

**Files:** Modify `src/fantasy_gm/api.py`; Create `scripts/setup_checkpointer.py`; Test `tests/test_api.py` (add a case)

- [ ] **Step 1: Write the checkpointer setup script** `scripts/setup_checkpointer.py`

```python
"""Create LangGraph checkpointer tables in Postgres (run once)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from langgraph.checkpoint.postgres import PostgresSaver  # noqa: E402

from fantasy_gm.config import get_settings  # noqa: E402

if __name__ == "__main__":
    with PostgresSaver.from_conn_string(get_settings().database_url) as cp:
        cp.setup()
    print("checkpointer tables created")
```

- [ ] **Step 2: Add the failing test** — the request threads `conversation_id` into the agent config

```python
def test_chat_threads_conversation_id(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import LeagueSettings
    from tests.support.fake_chat import FakeToolCallingModel
    from langchain_core.messages import AIMessage

    captured = {}

    class SpyAgent:
        def stream(self, inputs, config=None, stream_mode=None):
            captured["config"] = config
            return iter([{"agent": {"messages": [AIMessage(content="ok")]}}])

    monkeypatch.setattr(api, "_load_league",
                        lambda: LeagueSettings(league_key="428.l.1", format="category"))
    monkeypatch.setattr(api, "build_agent",
                        lambda **kw: SpyAgent())
    monkeypatch.setattr(api, "_make_model",
                        lambda: FakeToolCallingModel(responses=[AIMessage(content="ok")]))

    from fastapi.testclient import TestClient
    with TestClient(api.app).stream("POST", "/chat",
                                    json={"message": "hi", "conversation_id": "abc"}) as r:
        list(r.iter_text())
    assert captured["config"]["configurable"]["thread_id"] == "abc"
```

- [ ] **Step 3: Run it, confirm fail**

Run: `uv run pytest tests/test_api.py::test_chat_threads_conversation_id -v`
Expected: FAIL (the current `chat` passes no `config`).

- [ ] **Step 4: Update `chat` in `api.py`** to pass a per-conversation thread id

```python
    def gen():
        config = {"configurable": {"thread_id": req.conversation_id}}
        for chunk in agent.stream(
            {"messages": [HumanMessage(req.message)]},
            config=config,
            stream_mode="updates",
        ):
            ...  # (unchanged body)
```

(Production wiring: build the agent with a `PostgresSaver` checkpointer so the thread persists. Keep the checkpointer optional in `build_agent` so tests pass `None`. Document that `scripts/setup_checkpointer.py` must run once before first use.)

- [ ] **Step 5: Run tests, confirm pass**

Run: `uv run pytest tests/test_api.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/fantasy_gm/api.py scripts/setup_checkpointer.py tests/test_api.py
git commit -m "feat: thread conversation_id for Postgres-backed memory"
```

---

## Task 9: LangSmith eval scorers + harness

**Files:** Create `evals/scorers.py`, `evals/dataset.py`, `evals/run_evals.py`, `evals/__init__.py`; Test `tests/test_scorers.py`

The scorers are pure functions (unit-tested here). `dataset.py`/`run_evals.py` are thin LangSmith wrappers run manually (not unit-tested against the network).

- [ ] **Step 1: Write the failing scorer test**

```python
# tests/test_scorers.py
from evals.scorers import grounding_score, tool_trajectory_score


def test_grounding_score_penalizes_invented_players():
    known = {"Josh Hart"}
    assert grounding_score("Add Josh Hart.", known) == 1.0
    assert grounding_score("Add Josh Hart and LeBron James.", known) == 0.0


def test_tool_trajectory_requires_schedule_for_waiver():
    assert tool_trajectory_score(
        question_type="waiver",
        tools_called=["get_free_agents", "get_weekly_schedule"]) == 1.0
    assert tool_trajectory_score(
        question_type="waiver",
        tools_called=["get_free_agents"]) == 0.0   # missing schedule
    # a trade question must NOT hinge on weekly schedule
    assert tool_trajectory_score(
        question_type="trade",
        tools_called=["get_my_roster", "get_trends"]) == 1.0
```

- [ ] **Step 2: Run it, confirm fail**

Run: `uv run pytest tests/test_scorers.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `evals/scorers.py`**

```python
from fantasy_gm.guardrails import ungrounded_players


def grounding_score(answer: str, known_names: set[str]) -> float:
    """1.0 if every player named in the answer came from tool data, else 0.0."""
    return 0.0 if ungrounded_players(answer, known_names) else 1.0


def tool_trajectory_score(question_type: str, tools_called: list[str]) -> float:
    """Did the agent use the right tools/lens for the question type?"""
    called = set(tools_called)
    if question_type == "waiver":
        # short-term value must factor games this week
        return 1.0 if {"get_free_agents", "get_weekly_schedule"} <= called else 0.0
    if question_type == "trade":
        # long-term value: must use trends/roster, must NOT hinge on schedule
        needs = {"get_my_roster", "get_trends"} <= called
        return 1.0 if needs and "get_weekly_schedule" not in called else 0.0
    return 1.0
```

- [ ] **Step 4: Run it, confirm pass**

Run: `uv run pytest tests/test_scorers.py -v`
Expected: PASS.

- [ ] **Step 5: Write the LangSmith harness** `evals/dataset.py` and `evals/run_evals.py` (run manually; require `LANGCHAIN_API_KEY`)

```python
# evals/dataset.py
"""Seed a small LangSmith eval dataset of representative questions.
Run once: uv run python evals/dataset.py"""
from langsmith import Client

DATASET = "fantasy-gm-hero-questions"
EXAMPLES = [
    {"question": "Who should I pick up this week?", "type": "waiver"},
    {"question": "Should I trade my Haliburton for their Sabonis?", "type": "trade"},
    {"question": "Any buy-low candidates on the wire?", "type": "waiver"},
    # add ~15-25 total, covering waiver / trade / start-sit / trends
]

if __name__ == "__main__":
    client = Client()
    ds = client.create_dataset(DATASET)
    for ex in EXAMPLES:
        client.create_example(inputs={"question": ex["question"]},
                              metadata={"type": ex["type"]}, dataset_id=ds.id)
    print(f"seeded {len(EXAMPLES)} examples into {DATASET}")
```

```python
# evals/run_evals.py
"""Run the agent over the dataset and score with our scorers in LangSmith.
Run: uv run python evals/run_evals.py  (needs LANGCHAIN_API_KEY + a live agent)"""
from langsmith import Client

from evals.dataset import DATASET

if __name__ == "__main__":
    client = Client()
    print(f"Open the LangSmith UI to view runs for dataset '{DATASET}'.")
    print("Wire the agent target + scorers here once real Yahoo data is available;")
    print("scorers live in evals/scorers.py and are already unit-tested.")
    # Intentionally thin until live data exists — see Phase 3 (closed loop).
    _ = client, DATASET
```

- [ ] **Step 6: Commit**

```bash
git add evals/ tests/test_scorers.py
git commit -m "feat: eval scorers (grounding, tool-trajectory) + LangSmith harness"
```

---

## Task 10: README — run the agent + trade-offs

**Files:** Modify `README.md`

- [ ] **Step 1: Add a "Run the agent" section** documenting:

```
uv run python scripts/run_migrations.py
uv run python scripts/setup_checkpointer.py
uv run uvicorn fantasy_gm.api:app --reload    # POST /chat, GET /health
```

- [ ] **Step 2: Add a "Trade-offs" section** covering the real decisions:
  - Read-only agent (recommends; human executes) — why the LLM is never given write authority.
  - Grounding guardrail + tool-trajectory evals as the pre-ship quality gate ("prompt changes are gated by eval score").
  - `claude-opus-5` default, env-swappable to `claude-sonnet-5` for cost.
  - Keyed schedule API over free hidden endpoints (datacenter-IP blocking).
  - Postgres cache + nightly sync instead of hammering Yahoo (rate limits).
  - PaaS deploy now; note how it maps to AWS ECS/EKS + RDS + Secrets Manager (phase-2/enterprise).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README run-the-agent guide and engineering trade-offs"
```

---

## Phase 2 Done — Definition of Done

- [ ] `uv run pytest -v` green (all Phase 1 + agent_tools, agent, guardrails, api, scorers).
- [ ] `scripts/smoke_langgraph.py` passes (import surface confirmed / plan adjusted to match).
- [ ] `uv run uvicorn fantasy_gm.api:app` serves `/health` and a streaming `/chat` (verified end-to-end with a real Claude key against the fixtures once Yahoo data is swapped in, or with a manual smoke using the fake model).
- [ ] Eval scorers unit-tested; LangSmith dataset seed script present.
- [ ] README updated (run guide + trade-offs).

**What Phase 2 delivers:** a working, streaming conversational agent with guardrails and an eval harness — everything except a real Yahoo token (bridged by fixtures) and the React UI / deployment (Phase 3).

---

## Roadmap — Phase 3 (to be detailed after Phase 2)

- Vite + React streaming chat UI (consumes the SSE `tool`/`final` events).
- Deploy: Vercel (frontend) + Railway/Fly (backend + Postgres); live URL; secrets as env vars.
- Wire the existing Intent-Analysis system to this agent's live LangSmith traces (skill catalog = the toolbox); usage/gap dashboard populated as real usage accrues.
- Swap synthetic fixtures → real Yahoo data once API access is approved; re-verify parsers.
