# Fantasy GM Agent — Design Spec

**Status:** Approved design, pre-implementation
**Date:** 2026-09-07
**Author:** Barak Tal
**Purpose:** Portfolio project demonstrating Forward Deployed Engineer (FDE) capabilities — real-world API integration, agentic AI, productionization, observability, and a data-driven improvement loop.

---

## 1. One-line summary

An NBA fantasy-basketball conversational assistant: a LangGraph agent with a Yahoo Fantasy toolbox that answers any manager question (add/drop, trade evaluation, buy-low/sell-high, matchup analysis) by reasoning over live league data — with a games-played-aware value model, historical trends from Postgres, a streaming React chat UI, live deployment, pre-ship quality evals, and a closed-loop usage-intelligence system that mines real traces to find capability gaps and drive the roadmap.

## 2. Goals & non-goals

### Goals
- Demonstrate the full FDE lifecycle: **build → deploy → measure → find gaps → improve.**
- Prove **messy real-world integration** (Yahoo OAuth2 + legacy API).
- Prove **agentic AI** built the modern way (one agent + a toolbox, not N hardcoded features).
- Prove **observability & evaluation** (LangSmith traces + pre-ship scorers + usage analytics).
- Ship a **live, clickable demo** and a **client-grade README**.

### Non-goals (v1)
- The agent does **not** perform write actions on Yahoo (no auto add/drop/trade submission). It recommends; the human executes. Roadmap: write actions with human confirmation.
- No Kubernetes / VPC / EKS in v1. Cloud-portability is addressed *in writing* (README trade-offs) and left as documented phase-2.
- No multi-user auth system; single-user (the author's league) for the demo.

## 3. Target reader (why it exists)
FDE interviewers probe two things: *"Can you build and integrate it?"* and *"Can you tell if it's any good and operate it?"* This project is designed to answer both, with the closed usage-intelligence loop as the differentiator.

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  React Chat UI  (Vite + React, deployed on Vercel)            │
│  • one clean chat surface: streaming replies, live tool-status │
│    chips, rendered stat tables                                 │
└───────────────────────────┬─────────────────────────────────┘
                            │  HTTPS / JSON (+ streaming)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI Backend  (Python, Railway/Fly)                       │
│  • POST /chat  → runs agent, streams tokens + tool events      │
│  • GET  /health, /auth/yahoo/*  (OAuth callback)               │
│  • secrets via env vars, never in code                         │
└───────────┬───────────────────────────────┬─────────────────┘
            │                                │
            ▼                                ▼
┌───────────────────────────┐   ┌───────────────────────────────┐
│  LangGraph Agent           │   │  Yahoo Integration Layer       │
│  • plans → calls tools →   │──▶│  (all the mess, isolated)      │
│    reasons → streams answer│   │  • OAuth2 + token refresh      │
│  • league config seeded    │   │  • typed wrapper over legacy   │
│    (read once, cached)     │   │    XML/JSON, retries, cache    │
│                            │   └───────────────┬───────────────┘
│  TOOLBOX:                  │                   │
│   get_my_roster            │                   ▼
│   get_team(other)          │        ┌────────────────────────┐
│   get_free_agents          │        │  Yahoo Fantasy API      │
│   get_player_stats         │        │  (external, messy)      │
│   get_trends               │        └────────────────────────┘
│   get_weekly_schedule      │
│   refresh_league_settings  │
└───────────┬────────────────┘
            │ reads/writes
            ▼
┌───────────────────────────┐        ┌──────────────────────────┐
│  Postgres                  │        │  LangSmith (cloud)        │
│  • player_stat_snapshots   │        │  • full run traces        │
│  • weekly_schedule         │◀──auto─│  • pre-ship eval datasets │
│  • league_config           │ traces │  • cost / latency monitor │
│  • oauth_tokens            │        └───────────┬──────────────┘
│  • checkpointer (LangGraph)│                    │ traces ingested
└───────────▲────────────────┘                    ▼
            │                          ┌──────────────────────────┐
┌───────────┴───────────┐             │  Intent-Analysis System   │
│  Nightly sync job      │             │  (existing repo, reused)  │
│  stats + schedule →    │             │  • intent extraction      │
│  Postgres              │             │  • satisfaction scoring    │
└───────────────────────┘             │  • skill-gap quadrants →   │
                                       │    ROADMAP                 │
                                       └──────────────────────────┘
```

### Component boundaries
- **React UI** — one focused chat surface. Renders streamed tokens and lightweight tool-status events ("🔍 Checking the waiver wire…", "📈 Analyzing recent form…").
- **FastAPI backend** — thin transport layer; owns secrets, runs the agent, streams results, handles the OAuth callback.
- **LangGraph agent** — the brain. Plans a tool sequence per question, reasons, streams the answer. Read-only. League config is seeded into context (not re-fetched per question).
- **Yahoo integration layer** — the isolated "dirty" module. All OAuth/refresh/XML-parsing/rate-limit handling lives here behind clean typed functions.
- **Postgres** — durable state: stat snapshots, schedule, league config, tokens, and LangGraph's checkpointer (chat memory).
- **LangSmith** — cross-cutting observability + pre-ship eval backbone.
- **Intent-Analysis (reused)** — consumes LangSmith traces to produce usage intelligence and capability-gap analysis.

---

## 5. How the agent thinks (data flow)

The agent runs as a LangGraph loop: **MODEL node** (decide: call a tool, or answer) ↔ **TOOL node** (run tool, append result), repeating until it has enough to answer, then streams the final answer.

Example — *"Who should I pick up this week?"* (league format already known via seeded config):
1. `get_my_roster()` → current team + category stats
2. `get_free_agents()` → available players
3. `get_trends(window="14d")` → recent per-game form (reads Postgres)
4. `get_weekly_schedule()` → games remaining this week per player
5. Agent combines **form × games-this-week × team category needs** → recommends adds/drops with justification and a stat table.

The LLM chooses the tool sequence; the same loop serves every question type (trade eval, buy-low, matchup, etc.). This is the payoff of the toolbox architecture.

### Key domain rules
- **League config: read once, cache, refresh on demand.** Bootstrapped once into `league_config`, seeded into every conversation. User can say "refresh my league settings" → single `refresh_league_settings()` run overwrites the cache. The agent auto-adapts reasoning to 9-cat vs points because the format is in its context.
- **Two valuation modes — the agent must pick the right lens per question.**
  - **Short-term value** (waiver add/drop, streaming, start/sit): games-this-week aware.
    `short_term_value ≈ per_game_form × games_remaining_this_week`. A player with 4 games this week is worth ~2× the same player with 2 games. Compounds with recent trends (`get_trends` short window, e.g. 14d). This is the streaming edge.
  - **Long-term value** (evaluating trades for **core players**): a single week's schedule is *noise* and must be ignored. Uses rest-of-season / season-long production, sustained trends (long `get_trends` window / season averages), consistency, and role/usage — not weekly games count.
  - **Routing rule:** waiver/streaming/start-sit questions → short-term model; trade evaluation of core players → long-term model. The agent selects the lens based on question type and states which lens it used. This routing is itself a defensible interview talking point ("I don't let a favorable weekly schedule distort a season-long trade decision").

### Streaming
The backend streams both **answer tokens** (word-by-word) and **tool events** (status chips). This is most of what makes the UI feel impressive and maps 1:1 to the LangSmith trace.

### Memory
Conversation memory is handled by **LangGraph's checkpointer (Postgres-backed)**, keyed by `conversation_id`. No hand-built history table. Follow-ups ("who'd I drop for him?") reuse prior tool results.

---

## 6. Yahoo integration layer

```
yahoo_client/
  auth.py    → OAuth2 3-legged flow + automatic access-token refresh
  client.py  → typed wrapper: raw XML/JSON → Pydantic (Player, Team, LeagueSettings)
  cache.py   → short-TTL cache to respect rate limits
  errors.py  → one place that classifies Yahoo failures
```

- **OAuth2**: authorize once → access token (~1h) + long-lived refresh token. Store refresh token (encrypted), silently mint new access tokens on expiry.
- **Legacy API**: parse deeply-nested XML/JSON once into clean typed objects; keep all mess in one module.
- **Rate limits**: short-TTL cache (e.g. free-agent list 5 min) + polite retry-with-backoff.

### Day-0 de-risk spikes (before real building)
1. **OAuth spike** — authorize and pull own roster as JSON.
2. **Schedule spike** — confirm a reliable weekly NBA games-played source (Yahoo or a separate NBA schedule source).
Gate: both green → greenlight the sprint.

---

## 7. Data model (Postgres)

| Table | Job |
|---|---|
| `league_config` | one row: format, roster slots, categories, `cached_at` |
| `player_stat_snapshots` | daily per-player stats → powers `get_trends` |
| `weekly_schedule` | team × week → games count / games remaining |
| `oauth_tokens` | encrypted refresh token + current access token |
| *checkpointer tables* | **LangGraph-managed**, Postgres-backed → chat memory |

`player_stat_snapshots` + `weekly_schedule` are populated by the **nightly sync job** so tools read from Postgres instead of hammering Yahoo.

**Dropped (with rationale):** a custom `conversations` table (replaced by LangGraph checkpointer) and `agent_decision_logs` (LangSmith is the source of truth for what the agent did/cost; a decision log is only needed for a user-facing history/outcome-tracking feature → roadmap).

---

## 8. Error handling & guardrails

| Failure | Handling |
|---|---|
| Access token expired | `auth.py` auto-refreshes and retries once, transparently |
| Refresh token dead | Surface clear "please re-authorize" (can't self-heal) |
| Yahoo rate-limited / down | Exponential backoff; then serve last cached data + tell agent it's stale |
| A tool throws | Structured error to agent; agent retries a different tool or honestly says it couldn't fetch X — **never invents data** |
| LLM loops forever | Hard cap on tool-call iterations (≈8) + per-request cost ceiling |
| LLM hallucinates a player/stat | **Grounding rule**: agent may only cite players/stats returned by tools; enforced by system prompt + a grounding eval scorer |
| Streaming drops | UI retry; partial answer preserved |

Two guardrails define the trust story: the agent **cannot invent data** and **cannot take write actions**. The LLM is treated as a powerful-but-fallible component inside a controlled system.

---

## 9. Evaluation & usage intelligence (the differentiator)

Two complementary layers, deliberately deduped:

### 9a. Pre-ship quality gate (LangSmith, minimal)
A small saved dataset (~15–25 hero questions) + two **cheap rule-based scorers** run on every change:
- **Grounding** — every cited player/stat came from a tool result (catches hallucination).
- **Tool trajectory** — the right tools fired *and the right valuation lens was used*: "who to pick up" must call `get_weekly_schedule` (short-term); a core-player trade eval must use long-term trends/season data and must **not** hinge on this week's schedule.

Interview line: *"I treat prompt changes like code changes — they don't ship unless the eval score holds."*

### 9b. Post-ship usage intelligence (Intent-Analysis, reused — the closed loop)
The existing [Intent-Analysis](https://github.com/BarakTal1/Intent-Analysis) system consumes this agent's **LangSmith traces** and produces:
- **Intent distribution** — what users actually ask.
- **Satisfaction scoring (0–1, LLM-as-judge)** — this *replaces* a separate quality-judge; Intent-Analysis already does it.
- **Skill-gap quadrants (Core/Noisy/Niche/Redundant)** — the agent's **toolbox = the skill catalog**, so gaps map directly to roadmap items ("18% of questions are start/sit → no matching skill → build it").

```
Fantasy Assistant ──traces──▶ LangSmith ──ingested──▶ Intent-Analysis
       ▲                                                    │
       └──────── roadmap: data-driven capability gaps ◀─────┘
```

**Populating it with real usage:** no simulated corpus. The loop is wired at ship time and accumulates **genuine traces** from real use — the author (an active manager) using it through the season, plus optional league-mates. Trade-off accepted: the dashboard starts sparse and grows over weeks, so the closed loop is presented as *"instrumented and accumulating real usage"* and the rich gap-analysis screenshots come once enough real conversations exist. This is more credible than a seeded corpus, at the cost of not being demo-ready on day one.

### 9c. Traditional testing (focused, not coverage-chasing)
- Integration layer: unit tests with **recorded** Yahoo responses (replayed, never hit Yahoo); test parsing + token-refresh path.
- **Value model**: deterministic pure functions (`form × games`) tested hard — the analytical core.
- Tools: correct shape given mocked client data.
- One end-to-end smoke test against recorded data asserting a grounded answer.

---

## 10. Deployment
- **Frontend:** Vercel (live URL).
- **Backend + Postgres:** Railway or Fly.io (free/cheap tiers, minimal ops).
- **Secrets:** env vars on the platform; never in code.
- **Cloud-portability** addressed in the README trade-offs: how this maps to AWS ECS/EKS + RDS + Secrets Manager (documented phase-2, not built in v1).

---

## 11. Deliverables (portfolio surface)
1. Live clickable demo (public URL).
2. Client-grade README: Architecture (with diagram) · Security & Auth · Deployment Guide · Trade-offs.
3. LangSmith traces + eval scores (screenshots / description).
4. Intent-Analysis loop wired to live traces (dashboard + data-driven roadmap populated as real usage accumulates through the season).
5. Short demo GIF/Loom.

---

## 12. Sprint plan (~2.5–3 weeks, part-time)

The client-grade README grows throughout — each section written as its piece is built.

**Week 0 — De-risk & scaffold (a few evenings)**
- OAuth spike; schedule spike.
- Repo scaffold, `.env`/secrets pattern, local Postgres via Docker, LangSmith project connected.
- Gate: both spikes green → greenlight.

**Week 1 — Integration + data (FDE core)**
- `yahoo_client` (auth/refresh, typed wrapper, cache, errors).
- Postgres tables + nightly sync (stat snapshots + schedule).
- Toolbox on top; unit-test parsing + value math.
- README: Architecture + Security & Auth drafted.

**Week 2 — Agent + API + evals**
- LangGraph agent, toolbox bound, league-config seeding, iteration/cost caps, grounding guardrail.
- FastAPI `/chat` with token + tool-event streaming; Postgres checkpointer.
- LangSmith pre-ship dataset + grounding/trajectory scorers; tune prompt against them.
- README: Trade-offs section.

**Week 3 (half) — UI, deploy, closed loop, polish**
- React chat: streaming answers, live tool-status chips, clean stat tables.
- Deploy: Vercel + Railway/Fly; live URL.
- Wire Intent-Analysis: define skill catalog from toolbox, connect ingestion to the live LangSmith project. Real usage accumulates from here; capture dashboard screenshots once enough real conversations exist (may be post-sprint).
- README finish: Deployment Guide + diagram + demo GIF/Loom.
- Ship.

**Cut order if time runs short** (always keep a shippable thing): React polish → extra hero question-types → nightly-sync automation (run manually). **Never cut:** working agent, one grounded hero flow, pre-ship evals, live URL, README, and the Intent-Analysis loop (its whole point).

---

## 13. Tech stack
- **Agent:** LangGraph + LangChain, Claude (Anthropic) — consistent with Intent-Analysis.
- **Backend:** FastAPI (Python), Pydantic.
- **DB:** Postgres.
- **Frontend:** Vite + React.
- **Observability/Evals:** LangSmith.
- **Usage intelligence:** Intent-Analysis (existing; Claude LLM-judge + SBERT + FastAPI + ECharts).
- **Deploy:** Vercel + Railway/Fly.io; local dev via Docker Compose.

## 14. Open questions / to confirm during build
- Exact weekly-schedule data source (settled by the Week-0 spike).
- Anthropic model choice for the agent (default to the latest capable Claude; confirm at build time).
- Whether the pre-ship eval "recommendation quality" is fully delegated to Intent-Analysis satisfaction scoring or a lightweight judge is also kept in the gate.
