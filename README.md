# Fantasy GM Agent

A conversational AI assistant for NBA fantasy basketball. Ask it things like *"who should I pick up this week?"* or *"is this trade fair?"* and it reasons over your live Yahoo Fantasy league data — roster needs, recent player form, and how many games each player has this week — to give justified recommendations.

Built as a portfolio project demonstrating the full Forward Deployed Engineer lifecycle: **messy real-world integration → agentic AI → productionization → observability → a data-driven improvement loop.**

**🔗 Live demo: https://fantasy-gm-agent.vercel.app** — a three-tab app (Chat · Dashboard · Trade Analyzer) running on real 2024‑25 NBA player data in a demo league (Vercel frontend + Railway backend/Postgres). Ask the chat for waiver pickups, scan the dashboard, or analyze a trade.

> **Status:** Phases 1–6 built; **deployed and live**. Data layer, LangGraph/Claude agent, streaming FastAPI API, guardrails + evals, a polished React UI (Chat + Dashboard + Trade Analyzer, category **and** points leagues), and real-NBA demo data — deployed to a public URL (Sonnet 5 + per-IP rate limiting on the public endpoints). The one remaining external gate is **real Yahoo league data** (awaiting Yahoo's manual API approval; the integration is built + tested against spec-accurate fixtures and flips on with one env change). See [docs/design.md](docs/design.md) and [docs/plans/](docs/plans/).

## Architecture (target)

```
React chat UI  →  FastAPI (streaming)  →  LangGraph agent ── toolbox ──▶ Yahoo Fantasy API
                                              │                          (OAuth2 + refresh)
                                              ├──▶ Postgres (trends, schedule, config)
                                              └──▶ LangSmith (traces + evals)
                                                        │
                                          Intent-Analysis ◀── mines usage → roadmap
```

The design deliberately isolates all Yahoo messiness (OAuth token refresh, legacy JSON parsing, rate limits) behind one `yahoo_client` module, so the rest of the system only ever sees clean typed objects.

## What's built

**Phase 1 — data & integration layer**
- **`yahoo_client/`** — OAuth2 with transparent token refresh, typed parsers over Yahoo's nested JSON, short-TTL cache, error classification.
- **`db.py` + `db/schema.sql`** — Postgres store: league config, daily player stat snapshots, weekly schedule, tokens.
- **`value.py`** — two valuation modes: short-term (games-this-week-aware, for waivers/streaming) and long-term (season value, for core-player trades).
- **`sync.py`** — nightly sync of stats + NBA weekly schedule into Postgres.
- **`tools.py`** — the toolbox: league settings (read-once/refresh), trends, weekly schedule, roster/team/free agents.
- Weekly NBA games-played sourced from the [balldontlie API](https://www.balldontlie.io/) (keyed) — chosen over free hidden endpoints because those block datacenter IPs, which would break the cloud-hosted nightly sync.

**Phase 2 — agent, API & evals**
- **`agent.py` + `agent_tools.py` + `prompts.py`** — a LangGraph/Claude agent that plans tool calls and reasons, with the league format seeded into its system prompt. The toolbox is exposed as LangChain tools.
- **`api.py`** — FastAPI `POST /chat` streaming tool + answer events over SSE, `GET /health`.
- **`guardrails.py`** — grounding check that flags any player named in an answer that the tools didn't return.
- **`evals/`** — grounding + tool-trajectory scorers and a LangSmith dataset harness (the pre-ship quality gate).

**Phase 3 — React chat UI**
- **`frontend/`** — a Vite + React + TS chat: streaming answers, live tool-status chips, markdown stat tables, empty state, light/dark. Consumes the SSE stream.

**Phase 4 — dashboard, trade analyzer & full-league data**
- **`analytics.py` + `GET /analytics/dashboard`** — category profile (you vs league), streaming board (form × games), and buy-low/sell-high signals.
- **`trade.py` + `POST /trade/analyze`** — hybrid trade engine: deterministic per-category value delta → Claude writes an honest verdict grounded in that math (ACCEPT/DECLINE/COUNTER).
- **`frontend/` Dashboard + Trade views** — three-tab app (Chat · Dashboard · Trade) with hand-built dataviz charts (radar, ranked bars, diverging list, games heatmap), each with a legend + accessible table fallback.
- Backed by a seeded **12-team demo league** (`scripts/gen_demo_league.py`) so every view has substance before real Yahoo data.

## Security & Auth

- Secrets (`YAHOO_CLIENT_ID/SECRET`, API keys, DB URL) come from environment variables only, never committed. See `.env.example`.
- The agent is **read-only** by design: it recommends, the human executes. No roster/trade writes.
- OAuth refresh tokens are stored in Postgres; access tokens are refreshed transparently on expiry.

## Local development

Requires [uv](https://docs.astral.sh/uv/) and Docker.

```bash
cp .env.example .env      # then fill in your keys
docker compose up -d db   # local Postgres
uv run python scripts/run_migrations.py   # create tables
uv run pytest -v          # run the test suite
```

## Run the agent

Requires a running Postgres (`docker compose up -d db`) and, for real model calls, an `ANTHROPIC_API_KEY` in `.env` (tests use a fake model and need neither). Set `DEMO_MODE=true` to run against the committed fixtures before Yahoo API access is approved.

Backend (from repo root — `PYTHONPATH=src` because the package runs from `src/`):

```bash
uv run python scripts/run_migrations.py        # create/upgrade schema
uv run python scripts/seed_demo_data.py        # demo schedule + stat snapshots
PYTHONPATH=src uv run uvicorn fantasy_gm.api:app --port 8000   # POST /chat (SSE), /health
```

Frontend (from `frontend/`):

```bash
npm install && npm run dev                     # opens http://localhost:5173
```

`POST /chat` takes `{"message": str, "conversation_id": str}` and streams Server-Sent Events: `tool` (agent called a toolbox function), `token` (answer text delta), `final` (whole answer, fallback for non-streaming models), and `done`. `conversation_id` is threaded through as the LangGraph `thread_id`, and a `PostgresSaver` checkpointer (opened at app startup) persists conversation history across requests.

## Trade-offs

- **Read-only agent.** The LLM only ever calls read tools (roster, trends, schedule, free agents) and never has a path to submit a roster move or trade to Yahoo. It recommends; a human executes. This removes an entire class of "the agent did something irreversible" risk at the cost of one extra manual step per action.
- **Grounding guardrail + tool-trajectory evals as the pre-ship quality gate.** Every prompt or tool change is checked against LangSmith-scored evals (does the answer only mention players the tools actually returned; did the agent call the tools a reasonable trajectory would call) before it ships — a data-driven gate instead of "it looked fine in a manual test."
- **`claude-opus-5` by default, swappable via `AGENT_MODEL=claude-sonnet-5`.** Opus gives better reasoning over noisy fantasy trade-offs out of the box; Sonnet is a one-env-var downgrade for cost-sensitive deployments once the eval suite shows it holds up.
- **Keyed schedule API (balldontlie) over free hidden endpoints.** Free/unofficial NBA schedule endpoints tend to block datacenter IPs, which would silently break the nightly cloud sync. A keyed API costs a signup but keeps the sync reliable.
- **Postgres cache + nightly sync instead of calling Yahoo live per request.** League settings, stats, and schedule are cached and refreshed on a schedule so the agent never hammers Yahoo's rate-limited API mid-conversation; `get_league_settings` is read-once with an explicit `refresh_*` escape hatch.
- **PaaS deploy for now.** The current target is a simple PaaS (Postgres + one app process) to keep Phase 2/3 iteration fast. The same pieces map directly onto AWS for an enterprise deployment: ECS/EKS for the API process, RDS for Postgres, Secrets Manager for `YAHOO_CLIENT_SECRET`/`ANTHROPIC_API_KEY`/DB credentials — swapping infra, not architecture.

## Project docs

- [docs/design.md](docs/design.md) — full design spec (architecture, data flow, trade-offs).
- [docs/plans/](docs/plans/) — phased implementation plans.
