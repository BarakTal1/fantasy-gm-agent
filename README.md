# Fantasy GM Agent

A conversational AI assistant for NBA fantasy basketball. Ask it things like *"who should I pick up this week?"* or *"is this trade fair?"* and it reasons over your live Yahoo Fantasy league data — roster needs, recent player form, and how many games each player has this week — to give justified recommendations.

Built as a portfolio project demonstrating the full Forward Deployed Engineer lifecycle: **messy real-world integration → agentic AI → productionization → observability → a data-driven improvement loop.**

> **Status:** Phase 1 (foundation & data layer) complete. Yahoo Fantasy API access is pending Yahoo's manual approval; the integration is built and tested against spec-accurate fixtures and will swap to live data on approval. Agent, API, UI, and deployment are Phases 2–3. See [docs/design.md](docs/design.md) and [docs/plans/](docs/plans/).

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

## What's built (Phase 1)

- **`yahoo_client/`** — OAuth2 with transparent token refresh, typed parsers over Yahoo's nested JSON, short-TTL cache, error classification.
- **`db.py` + `db/schema.sql`** — Postgres store: league config, daily player stat snapshots, weekly schedule, tokens.
- **`value.py`** — two valuation modes: short-term (games-this-week-aware, for waivers/streaming) and long-term (season value, for core-player trades).
- **`sync.py`** — nightly sync of stats + NBA weekly schedule into Postgres.
- **`tools.py`** — the agent's toolbox: league settings (read-once/refresh), trends, weekly schedule.
- Weekly NBA games-played sourced from the [balldontlie API](https://www.balldontlie.io/) (keyed) — chosen over free hidden endpoints because those block datacenter IPs, which would break the cloud-hosted nightly sync.

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

## Project docs

- [docs/design.md](docs/design.md) — full design spec (architecture, data flow, trade-offs).
- [docs/plans/](docs/plans/) — phased implementation plans.
