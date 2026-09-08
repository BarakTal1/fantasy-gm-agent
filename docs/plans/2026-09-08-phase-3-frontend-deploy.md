# Phase 3 — Frontend, Streaming & Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Ship the polished React chat UI (the design in `docs/` — "AI-Native UI", Inter, blue+green, streaming tool chips) talking to the FastAPI SSE backend, upgrade the backend to stream answer tokens, and provide runbooks to deploy a live URL, wire the Intent-Analysis loop, and swap fixtures → real Yahoo data on approval.

**Architecture:** A Vite + React + TypeScript app in `frontend/`, styled with CSS custom-property design tokens (light/dark), consuming the backend `POST /chat` SSE stream via a fetch-based reader (browser `EventSource` can't POST). Logic (SSE parsing, message reducer, tool→label mapping, theme) is unit-tested with Vitest; components get render tests with Testing Library. The backend gains CORS and token-level streaming. Deploy is Vercel (frontend) + Railway/Fly (backend + Postgres). Determinism boundary: token streaming from a real LLM is validated live; unit tests cover the tool-events + final-answer path and all frontend logic.

**Tech Stack:** Backend (existing) + FastAPI CORS. Frontend: Vite, React 18, TypeScript, `react-markdown` + `remark-gfm` (tables), `lucide-react` (icons), Vitest + `@testing-library/react` + `jsdom`. Plain CSS with custom properties (no Tailwind — full control over the custom chat surface).

**⚠️ Note:** run all frontend commands from `frontend/`. The backend keeps using `uv` from repo root.

---

## File Structure

```
src/fantasy_gm/api.py                 # (modify) CORS + token streaming
frontend/
  index.html
  package.json  vite.config.ts  tsconfig.json  vitest.config.ts
  src/
    main.tsx                          # React entry
    App.tsx                           # compose everything, run the chat loop
    styles/tokens.css                 # design tokens (light/dark) + base
    styles/app.css                    # component styles
    lib/sse.ts                        # postChatStream: POST + parse SSE events
    lib/toolMeta.ts                   # tool name -> {label, icon}
    state/messages.ts                 # message reducer + types
    hooks/useTheme.ts                 # light/dark with localStorage + system
    components/Header.tsx
    components/ThemeToggle.tsx
    components/EmptyState.tsx
    components/MessageList.tsx
    components/MessageBubble.tsx      # markdown + styled stat tables
    components/ToolChips.tsx
    components/TypingIndicator.tsx
    components/Composer.tsx
    components/ErrorBanner.tsx
  src/__tests__/                      # sse, messages, toolMeta, useTheme, components
```

---

## Task B1: Backend — CORS + token streaming

**Files:** Modify `src/fantasy_gm/api.py`; Test `tests/test_api.py` (add cases)

- [ ] **Step 1: Add the failing test** (append to `tests/test_api.py`)

```python
def test_cors_headers_present():
    from fantasy_gm import api
    from fastapi.testclient import TestClient
    r = TestClient(api.app).options(
        "/chat",
        headers={"Origin": "http://localhost:5173",
                 "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin") in {"*", "http://localhost:5173"}
```

- [ ] **Step 2: Run it, confirm fail**

Run: `uv run pytest tests/test_api.py::test_cors_headers_present -v`
Expected: FAIL (no CORS header).

- [ ] **Step 3: Add CORS + token streaming to `api.py`**

Add near the top, after `app = FastAPI(...)`:

```python
from fastapi.middleware.cors import CORSMiddleware

_ALLOWED_ORIGINS = [
    "http://localhost:5173",   # Vite dev
    "http://127.0.0.1:5173",
]
# In production, add the deployed frontend origin via env (see deploy runbook).
import os
if os.getenv("FRONTEND_ORIGIN"):
    _ALLOWED_ORIGINS.append(os.environ["FRONTEND_ORIGIN"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Then upgrade the `chat` generator to emit `token` events (answer text deltas) in addition to `tool` and `final`, using multiple stream modes:

```python
    def gen():
        config = {"configurable": {"thread_id": req.conversation_id}}
        emitted_token = False
        for mode, chunk in agent.stream(
            {"messages": [HumanMessage(req.message)]},
            config=config,
            stream_mode=["updates", "messages"],
        ):
            if mode == "messages":
                msg, _meta = chunk
                text = _chunk_text(msg)
                tool_calls = getattr(msg, "tool_calls", None)
                if text and not tool_calls:
                    emitted_token = True
                    yield _sse("token", {"text": text})
            elif mode == "updates":
                for _node, update in chunk.items():
                    msgs = update.get("messages", []) if isinstance(update, dict) else []
                    for m in msgs:
                        for tc in getattr(m, "tool_calls", None) or []:
                            yield _sse("tool", {"name": tc["name"]})
                        if isinstance(m, AIMessage) and _text(m.content) and not emitted_token:
                            # fallback for non-streaming models: send the whole answer
                            yield _sse("final", {"text": _text(m.content)})
        yield _sse("done", {})
```

Add these helpers to `api.py`:

```python
def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content
                   if isinstance(b, dict) and b.get("type") == "text")


def _chunk_text(msg) -> str:
    """Text delta from a streamed message chunk (Opus 5 returns block lists)."""
    return _text(getattr(msg, "content", "") or "")
```

Note: `AIMessage` is already imported. The frontend renders `token` deltas if any arrive, else falls back to the `final` event — so both streaming and non-streaming models work. Token streaming is validated by the live smoke; unit tests cover the tool + final path with the fake model.

- [ ] **Step 4: Update BOTH existing API tests for the new `(mode, chunk)` tuple shape.** With `stream_mode=["updates","messages"]`, `agent.stream(...)` yields `(mode, chunk)` tuples, so:
  - `test_chat_streams_final_answer`: still asserts the answer text appears in the streamed body (now via `token` or `final`). If needed, search the body for the substring rather than an exact event.
  - `test_chat_threads_conversation_id`: the `SpyAgent.stream` stub must now yield tuples, e.g. `return iter([("updates", {"agent": {"messages": [AIMessage(content="ok")]}})])`, and still capture `config`. Assert `config["configurable"]["thread_id"] == "abc"` as before.

- [ ] **Step 5: Run the API tests, confirm pass**

Run: `uv run pytest tests/test_api.py -v`
Expected: PASS (CORS + streaming + thread-id).

- [ ] **Step 6: Commit**

```bash
git add src/fantasy_gm/api.py tests/test_api.py
git commit -m "feat: CORS + token-level SSE streaming on /chat"
```

---

## Task B2: Wire live conversation memory (PostgresSaver)

**Files:** Modify `src/fantasy_gm/api.py`; Test `tests/test_api.py` (add a case)

Closes the Phase 2 gap: threads the `conversation_id` into a real Postgres checkpointer so follow-ups persist. The saver is opened once for the app's lifetime via FastAPI lifespan and injected into `build_agent`. Tests don't trigger lifespan (plain `TestClient(app)` without `with`), so they stay DB-free and `_checkpointer` is `None`.

- [ ] **Step 1: Add the failing test** — `chat` must build the agent with the process checkpointer when one exists

```python
def test_chat_passes_checkpointer(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import LeagueSettings
    from langchain_core.messages import AIMessage
    seen = {}

    class SpyAgent:
        def stream(self, inputs, config=None, stream_mode=None):
            return iter([("updates", {"agent": {"messages": [AIMessage(content="ok")]}})])

    monkeypatch.setattr(api, "_load_league",
                        lambda: LeagueSettings(league_key="428.l.1", format="category"))
    monkeypatch.setattr(api, "_make_model", lambda: object())
    monkeypatch.setattr(api, "_checkpointer", "SENTINEL_CP")
    monkeypatch.setattr(api, "build_agent",
                        lambda **kw: (seen.update(kw), SpyAgent())[1])

    from fastapi.testclient import TestClient
    with TestClient(api.app).stream("POST", "/chat",
                                    json={"message": "hi", "conversation_id": "c"}) as r:
        list(r.iter_text())
    assert seen["checkpointer"] == "SENTINEL_CP"
```

- [ ] **Step 2: Run it, confirm fail** — `chat` currently omits `checkpointer`.

- [ ] **Step 3: Implement in `api.py`** — a module-level checkpointer opened via lifespan, passed to `build_agent`

```python
from contextlib import asynccontextmanager
from langgraph.checkpoint.postgres import PostgresSaver

_checkpointer = None  # set at startup in production; stays None under tests


@asynccontextmanager
async def lifespan(_app):
    global _checkpointer
    cm = PostgresSaver.from_conn_string(get_settings().database_url)
    _checkpointer = cm.__enter__()
    _checkpointer.setup()
    try:
        yield
    finally:
        cm.__exit__(None, None, None)
        _checkpointer = None
```

Pass `lifespan=lifespan` to the `FastAPI(...)` constructor, and in `chat` build with the checkpointer:

```python
    agent = build_agent(league=_load_league(), league_key=LEAGUE_KEY,
                        my_team_key=MY_TEAM_KEY, model=_make_model(),
                        checkpointer=_checkpointer)
```

Note: live persistence is validated by the manual live check (Task F7) with two messages in one conversation; unit tests only assert the checkpointer is passed through.

- [ ] **Step 4: Run it, confirm pass**; also re-run the full API suite.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/api.py tests/test_api.py
git commit -m "feat: persist conversation memory via Postgres checkpointer (lifespan)"
```

---

## Task F0: Scaffold the Vite + React + TS app

**Files:** create `frontend/` project

- [ ] **Step 1: Scaffold**

```bash
cd ~/Documents/fantasy-gm-agent
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
npm install react-markdown remark-gfm lucide-react
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom @testing-library/user-event
```

- [ ] **Step 2: Add `frontend/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", globals: true, setupFiles: "./src/setupTests.ts" },
});
```

- [ ] **Step 3: Add `frontend/src/setupTests.ts`**

```ts
import "@testing-library/jest-dom";
```

- [ ] **Step 4: Add scripts to `frontend/package.json`** (merge into `"scripts"`)

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 5: Write a smoke test** `frontend/src/__tests__/smoke.test.ts`

```ts
import { describe, it, expect } from "vitest";
describe("smoke", () => { it("runs", () => { expect(1 + 1).toBe(2); }); });
```

- [ ] **Step 6: Run it**

Run (from `frontend/`): `npm test`
Expected: 1 passing test.

- [ ] **Step 7: Add `.gitignore` entries** for `frontend/node_modules`, `frontend/dist` (create `frontend/.gitignore` — Vite adds one; ensure `node_modules` and `dist` are in it).

- [ ] **Step 8: Commit**

```bash
cd ~/Documents/fantasy-gm-agent
git add frontend
git commit -m "chore: scaffold Vite + React + TS frontend with Vitest"
```

---

## Task F1: Design tokens + theme hook

**Files:** Create `frontend/src/styles/tokens.css`, `frontend/src/hooks/useTheme.ts`; Test `frontend/src/__tests__/useTheme.test.ts`

- [ ] **Step 1: Write `frontend/src/styles/tokens.css`** (the design system as CSS variables)

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --font: 'Inter', system-ui, sans-serif;
  --primary: #2563EB; --primary-hover: #1D4ED8; --on-primary: #FFFFFF;
  --indigo: #6366F1; --accent: #059669;
  --bg: #FFFFFF; --surface: #F1F5FD; --surface-2: #FFFFFF;
  --text: #0F172A; --muted: #64748B; --border: #E4ECFC;
  --danger: #DC2626; --ring: #2563EB;
  --radius: 14px; --radius-sm: 10px;
  --shadow: 0 1px 2px rgba(15,23,42,.06), 0 4px 16px rgba(15,23,42,.06);
}
:root[data-theme="dark"] {
  --primary: #3B82F6; --primary-hover: #60A5FA; --on-primary: #0B1220;
  --indigo: #818CF8; --accent: #10B981;
  --bg: #0B1220; --surface: #111A2E; --surface-2: #0F1729;
  --text: #E5EDF7; --muted: #94A3B8; --border: #1E293B;
  --danger: #F87171; --ring: #3B82F6;
  --shadow: 0 1px 2px rgba(0,0,0,.4), 0 4px 20px rgba(0,0,0,.35);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --primary: #3B82F6; --primary-hover: #60A5FA; --on-primary: #0B1220;
    --indigo: #818CF8; --accent: #10B981;
    --bg: #0B1220; --surface: #111A2E; --surface-2: #0F1729;
    --text: #E5EDF7; --muted: #94A3B8; --border: #1E293B;
    --danger: #F87171; --ring: #3B82F6;
    --shadow: 0 1px 2px rgba(0,0,0,.4), 0 4px 20px rgba(0,0,0,.35);
  }
}
* { box-sizing: border-box; }
body { margin: 0; font-family: var(--font); background: var(--bg); color: var(--text); }
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
```

- [ ] **Step 2: Write the failing test** `frontend/src/__tests__/useTheme.test.ts`

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTheme } from "../hooks/useTheme";

beforeEach(() => { localStorage.clear(); document.documentElement.removeAttribute("data-theme"); });

describe("useTheme", () => {
  it("toggles and persists", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current.toggle());
    const t = result.current.theme;
    expect(["light", "dark"]).toContain(t);
    expect(document.documentElement.getAttribute("data-theme")).toBe(t);
    expect(localStorage.getItem("theme")).toBe(t);
  });
});
```

- [ ] **Step 3: Run it, confirm fail** — Run (from `frontend/`): `npm test -- useTheme` → FAIL (module missing).

- [ ] **Step 4: Implement `frontend/src/hooks/useTheme.ts`**

```ts
import { useCallback, useEffect, useState } from "react";

type Theme = "light" | "dark";

function initial(): Theme {
  const saved = localStorage.getItem("theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(initial);
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);
  const toggle = useCallback(() => setTheme((t) => (t === "dark" ? "light" : "dark")), []);
  return { theme, toggle };
}
```

- [ ] **Step 5: Run it, confirm pass**; **Step 6: Commit**

```bash
git add frontend/src/styles/tokens.css frontend/src/hooks/useTheme.ts frontend/src/__tests__/useTheme.test.ts
git commit -m "feat(ui): design tokens (light/dark) and theme hook"
```

---

## Task F2: SSE-over-fetch client

**Files:** Create `frontend/src/lib/sse.ts`; Test `frontend/src/__tests__/sse.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect, vi } from "vitest";
import { parseSSE } from "../lib/sse";

describe("parseSSE", () => {
  it("dispatches events with parsed data", () => {
    const events: Array<[string, any]> = [];
    const feed = parseSSE((ev, data) => events.push([ev, data]));
    feed('event: tool\ndata: {"name":"get_free_agents"}\n\n');
    feed('event: token\ndata: {"text":"Pick "}\n\nevent: token\ndata: {"text":"Hart"}\n\n');
    feed('event: done\ndata: {}\n\n');
    expect(events).toEqual([
      ["tool", { name: "get_free_agents" }],
      ["token", { text: "Pick " }],
      ["token", { text: "Hart" }],
      ["done", {}],
    ]);
  });
});
```

- [ ] **Step 2: Run it, confirm fail**; **Step 3: Implement `frontend/src/lib/sse.ts`**

```ts
type Handler = (event: string, data: any) => void;

/** Feed raw SSE text chunks; buffers partial frames and dispatches complete ones. */
export function parseSSE(onEvent: Handler) {
  let buf = "";
  return (chunk: string) => {
    buf += chunk;
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let event = "message";
      const dataLines: string[] = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (dataLines.length) {
        let data: any = dataLines.join("\n");
        try { data = JSON.parse(data); } catch { /* keep string */ }
        onEvent(event, data);
      }
    }
  };
}

export interface ChatCallbacks {
  onTool?: (name: string) => void;
  onToken?: (text: string) => void;
  onFinal?: (text: string) => void;
  onDone?: () => void;
  onError?: (err: unknown) => void;
}

/** POST to /chat and stream SSE events (browser EventSource cannot POST). */
export async function postChatStream(
  baseUrl: string,
  body: { message: string; conversation_id: string },
  cb: ChatCallbacks,
  signal?: AbortSignal,
) {
  try {
    const res = await fetch(`${baseUrl}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
    const feed = parseSSE((ev, data) => {
      if (ev === "tool") cb.onTool?.(data.name);
      else if (ev === "token") cb.onToken?.(data.text);
      else if (ev === "final") cb.onFinal?.(data.text);
      else if (ev === "done") cb.onDone?.();
    });
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      feed(dec.decode(value, { stream: true }));
    }
    cb.onDone?.();
  } catch (err) {
    if ((err as Error).name !== "AbortError") cb.onError?.(err);
  }
}
```

- [ ] **Step 4: Run it, confirm pass**; **Step 5: Commit**

```bash
git add frontend/src/lib/sse.ts frontend/src/__tests__/sse.test.ts
git commit -m "feat(ui): SSE-over-fetch chat stream client"
```

---

## Task F3: Tool → label/icon metadata

**Files:** Create `frontend/src/lib/toolMeta.ts`; Test `frontend/src/__tests__/toolMeta.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from "vitest";
import { toolMeta } from "../lib/toolMeta";

describe("toolMeta", () => {
  it("maps known tools to friendly labels", () => {
    expect(toolMeta("get_free_agents").label).toBe("Scanning the waiver wire");
    expect(toolMeta("get_weekly_schedule").label).toBe("Counting games this week");
    expect(toolMeta("get_trends").label).toBe("Analyzing recent form");
  });
  it("falls back for unknown tools", () => {
    expect(toolMeta("mystery").label).toBe("Working…");
  });
});
```

- [ ] **Step 2: Run it, confirm fail**; **Step 3: Implement `frontend/src/lib/toolMeta.ts`**

```ts
import { ClipboardList, Search, TrendingUp, CalendarDays, Settings, Loader,
         type LucideIcon } from "lucide-react";

const MAP: Record<string, { label: string; icon: LucideIcon }> = {
  get_my_roster: { label: "Reading your roster", icon: ClipboardList },
  get_free_agents: { label: "Scanning the waiver wire", icon: Search },
  get_trends: { label: "Analyzing recent form", icon: TrendingUp },
  get_weekly_schedule: { label: "Counting games this week", icon: CalendarDays },
  get_league_settings: { label: "Checking league settings", icon: Settings },
};

export function toolMeta(name: string) {
  return MAP[name] ?? { label: "Working…", icon: Loader };
}
```

- [ ] **Step 4: Run it, confirm pass**; **Step 5: Commit**

```bash
git add frontend/src/lib/toolMeta.ts frontend/src/__tests__/toolMeta.test.ts
git commit -m "feat(ui): tool name to friendly label/icon mapping"
```

---

## Task F4: Message state reducer

**Files:** Create `frontend/src/state/messages.ts`; Test `frontend/src/__tests__/messages.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from "vitest";
import { chatReducer, initialState, type ChatAction } from "../state/messages";

function run(actions: ChatAction[]) {
  return actions.reduce(chatReducer, initialState);
}

describe("chatReducer", () => {
  it("adds a user message and opens an assistant turn", () => {
    const s = run([{ type: "send", text: "hi" }]);
    expect(s.messages[0]).toMatchObject({ role: "user", content: "hi" });
    expect(s.messages[1]).toMatchObject({ role: "assistant", streaming: true });
    expect(s.streaming).toBe(true);
  });
  it("records tool calls then streams tokens", () => {
    const s = run([
      { type: "send", text: "hi" },
      { type: "tool", name: "get_trends" },
      { type: "token", text: "Pick " },
      { type: "token", text: "Hart" },
      { type: "done" },
    ]);
    const a = s.messages[1];
    expect(a.tools).toEqual(["get_trends"]);
    expect(a.content).toBe("Pick Hart");
    expect(a.streaming).toBe(false);
    expect(s.streaming).toBe(false);
  });
  it("final replaces content when no tokens streamed", () => {
    const s = run([{ type: "send", text: "hi" }, { type: "final", text: "Answer" },
                   { type: "done" }]);
    expect(s.messages[1].content).toBe("Answer");
  });
  it("captures errors on the open assistant turn", () => {
    const s = run([{ type: "send", text: "hi" }, { type: "error", message: "boom" }]);
    expect(s.messages[1].error).toBe("boom");
    expect(s.streaming).toBe(false);
  });
});
```

- [ ] **Step 2: Run it, confirm fail**; **Step 3: Implement `frontend/src/state/messages.ts`**

```ts
export interface Message {
  role: "user" | "assistant";
  content: string;
  tools?: string[];
  streaming?: boolean;
  error?: string;
}
export interface ChatState { messages: Message[]; streaming: boolean; }
export const initialState: ChatState = { messages: [], streaming: false };

export type ChatAction =
  | { type: "send"; text: string }
  | { type: "tool"; name: string }
  | { type: "token"; text: string }
  | { type: "final"; text: string }
  | { type: "done" }
  | { type: "error"; message: string };

function patchLast(s: ChatState, fn: (m: Message) => Message): ChatState {
  const messages = s.messages.slice();
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "assistant") { messages[i] = fn(messages[i]); break; }
  }
  return { ...s, messages };
}

export function chatReducer(s: ChatState, a: ChatAction): ChatState {
  switch (a.type) {
    case "send":
      return {
        streaming: true,
        messages: [...s.messages,
          { role: "user", content: a.text },
          { role: "assistant", content: "", tools: [], streaming: true }],
      };
    case "tool":
      return patchLast(s, (m) => ({ ...m, tools: [...(m.tools ?? []), a.name] }));
    case "token":
      return patchLast(s, (m) => ({ ...m, content: m.content + a.text }));
    case "final":
      return patchLast(s, (m) => (m.content ? m : { ...m, content: a.text }));
    case "done":
      return { ...patchLast(s, (m) => ({ ...m, streaming: false })), streaming: false };
    case "error":
      return { ...patchLast(s, (m) => ({ ...m, streaming: false, error: a.message })),
               streaming: false };
    default:
      return s;
  }
}
```

- [ ] **Step 4: Run it, confirm pass**; **Step 5: Commit**

```bash
git add frontend/src/state/messages.ts frontend/src/__tests__/messages.test.ts
git commit -m "feat(ui): chat message reducer (tools, tokens, final, error)"
```

---

## Task F5: Presentational components

**Files:** Create the components listed below + `frontend/src/styles/app.css`; Test `frontend/src/__tests__/components.test.tsx`

- [ ] **Step 1: Write the failing render test**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MessageBubble } from "../components/MessageBubble";
import { EmptyState } from "../components/EmptyState";
import { Composer } from "../components/Composer";

describe("components", () => {
  it("renders an assistant markdown table", () => {
    render(<MessageBubble m={{ role: "assistant",
      content: "| P | AST |\n|---|---|\n| Hart | 5.2 |" }} />);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("Hart")).toBeInTheDocument();
  });
  it("empty state fires an example prompt", async () => {
    const onPick = vi.fn();
    render(<EmptyState onPick={onPick} />);
    await userEvent.click(screen.getByText(/who should i pick up/i));
    expect(onPick).toHaveBeenCalled();
  });
  it("composer submits on send", async () => {
    const onSend = vi.fn();
    render(<Composer streaming={false} onSend={onSend} onStop={() => {}} />);
    await userEvent.type(screen.getByRole("textbox"), "hello");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    expect(onSend).toHaveBeenCalledWith("hello");
  });
});
```

- [ ] **Step 2: Run it, confirm fail** (from `frontend/`): `npm test -- components`

- [ ] **Step 3: Implement the components.** Full code for each:

`frontend/src/components/MessageBubble.tsx`
```tsx
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "../state/messages";
import { ToolChips } from "./ToolChips";

export function MessageBubble({ m }: { m: Message }) {
  if (m.role === "user")
    return <div className="row end"><div className="bubble user">{m.content}</div></div>;
  return (
    <div className="row start">
      <div className="bubble assistant">
        {m.tools && m.tools.length > 0 && (
          <ToolChips tools={m.tools} active={!!m.streaming} />
        )}
        {m.error ? (
          <div className="err">{m.error}</div>
        ) : (
          <div className="md" aria-live="polite">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
            {m.streaming && !m.content && <span className="caret" />}
          </div>
        )}
      </div>
    </div>
  );
}
```

`frontend/src/components/ToolChips.tsx`
```tsx
import { Check } from "lucide-react";
import { toolMeta } from "../lib/toolMeta";

export function ToolChips({ tools, active }: { tools: string[]; active: boolean }) {
  return (
    <div className="chips">
      {tools.map((name, i) => {
        const { label, icon: Icon } = toolMeta(name);
        const last = i === tools.length - 1;
        const running = active && last;
        return (
          <span className="chip" key={`${name}-${i}`}>
            {running ? <Icon size={14} className="spin" /> : <Check size={14} />}
            {label}
          </span>
        );
      })}
    </div>
  );
}
```

`frontend/src/components/TypingIndicator.tsx`
```tsx
export function TypingIndicator() {
  return (
    <div className="typing" aria-label="Assistant is thinking">
      <span /><span /><span />
    </div>
  );
}
```

`frontend/src/components/Composer.tsx`
```tsx
import { useState } from "react";
import { Send, Square } from "lucide-react";

export function Composer({ streaming, onSend, onStop }: {
  streaming: boolean; onSend: (t: string) => void; onStop: () => void;
}) {
  const [value, setValue] = useState("");
  const submit = () => { const t = value.trim(); if (t) { onSend(t); setValue(""); } };
  return (
    <form className="composer" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <textarea
        rows={1} value={value} placeholder="Ask about your team…"
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
        }}
        aria-label="Message"
      />
      {streaming ? (
        <button type="button" className="icon-btn stop" onClick={onStop} aria-label="Stop">
          <Square size={18} />
        </button>
      ) : (
        <button type="submit" className="icon-btn send" aria-label="Send">
          <Send size={18} />
        </button>
      )}
    </form>
  );
}
```

`frontend/src/components/EmptyState.tsx`
```tsx
const EXAMPLES = [
  "Who should I pick up this week?",
  "Is trading Haliburton for Sabonis fair?",
  "Any buy-low targets on the wire?",
  "Who should I start tonight?",
];
export function EmptyState({ onPick }: { onPick: (t: string) => void }) {
  return (
    <div className="empty">
      <h1>Your fantasy GM, on call.</h1>
      <p>Ask about waivers, trades, streaming, and buy-low targets — grounded in your league.</p>
      <div className="examples">
        {EXAMPLES.map((e) => (
          <button key={e} className="example" onClick={() => onPick(e)}>{e}</button>
        ))}
      </div>
    </div>
  );
}
```

`frontend/src/components/Header.tsx`
```tsx
import { ThemeToggle } from "./ThemeToggle";

export function Header({ theme, onToggle }: { theme: string; onToggle: () => void }) {
  return (
    <header className="header">
      <div className="brand"><span className="mark" />Fantasy GM</div>
      <span className="league">Dubs Dynasty · 9-cat</span>
      <ThemeToggle theme={theme} onToggle={onToggle} />
    </header>
  );
}
```

`frontend/src/components/ThemeToggle.tsx`
```tsx
import { Moon, Sun } from "lucide-react";
export function ThemeToggle({ theme, onToggle }: { theme: string; onToggle: () => void }) {
  return (
    <button className="icon-btn ghost" onClick={onToggle}
            aria-label={theme === "dark" ? "Switch to light" : "Switch to dark"}>
      {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}
```

`frontend/src/components/ErrorBanner.tsx`
```tsx
export function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="banner" role="alert">
      {message} <button onClick={onRetry}>Retry</button>
    </div>
  );
}
```

- [ ] **Step 4: Write `frontend/src/styles/app.css`** implementing the design (bubbles, chips, typing pulse, composer, tables, empty state, header). Key rules:

```css
.app { display: flex; flex-direction: column; min-height: 100dvh; max-width: 820px;
  margin: 0 auto; }
.header { position: sticky; top: 0; display: flex; align-items: center; gap: 12px;
  padding: 12px 16px; background: var(--bg); border-bottom: 1px solid var(--border); z-index: 10; }
.brand { font-weight: 700; display: flex; align-items: center; gap: 8px; }
.mark { width: 18px; height: 18px; border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, var(--accent), var(--primary)); }
.league { color: var(--muted); font-size: 13px; }
.header .icon-btn.ghost { margin-left: auto; }
.list { flex: 1; overflow-y: auto; padding: 20px 16px; display: flex; flex-direction: column; gap: 14px; }
.row { display: flex; } .row.end { justify-content: flex-end; } .row.start { justify-content: flex-start; }
.bubble { max-width: 88%; padding: 12px 14px; border-radius: var(--radius); box-shadow: var(--shadow); }
.bubble.user { background: var(--primary); color: var(--on-primary); border-bottom-right-radius: 4px; }
.bubble.assistant { background: var(--surface); border: 1px solid var(--border); border-bottom-left-radius: 4px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.chip { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--muted);
  background: var(--surface-2); border: 1px solid var(--border); border-radius: 999px; padding: 4px 10px; }
.spin { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }
.md :is(p,ul,ol) { margin: 6px 0; line-height: 1.6; }
.md table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; display: block; overflow-x: auto; }
.md th, .md td { border: 1px solid var(--border); padding: 6px 10px; text-align: left; white-space: nowrap; }
.md thead th { position: sticky; top: 0; background: var(--surface-2); }
.md tbody tr:nth-child(odd) { background: color-mix(in srgb, var(--surface-2) 60%, transparent); }
.caret { display: inline-block; width: 8px; height: 1em; background: var(--primary);
  animation: blink 1s step-end infinite; vertical-align: -2px; } @keyframes blink { 50% { opacity: 0; } }
.typing { display: inline-flex; gap: 4px; } .typing span { width: 6px; height: 6px; border-radius: 50%;
  background: var(--muted); animation: pulse 1.2s infinite; } .typing span:nth-child(2){animation-delay:.2s}
.typing span:nth-child(3){animation-delay:.4s} @keyframes pulse { 0%,60%,100%{opacity:.3} 30%{opacity:1} }
.composer { position: sticky; bottom: 0; display: flex; gap: 8px; padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
  background: var(--bg); border-top: 1px solid var(--border); }
.composer textarea { flex: 1; resize: none; font: inherit; padding: 12px 14px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--surface-2); color: var(--text); max-height: 160px; }
.composer textarea:focus-visible, .icon-btn:focus-visible, .example:focus-visible { outline: 2px solid var(--ring); outline-offset: 2px; }
.icon-btn { min-width: 44px; min-height: 44px; display: grid; place-items: center; border: none; border-radius: var(--radius-sm);
  background: var(--primary); color: var(--on-primary); cursor: pointer; }
.icon-btn.ghost { background: transparent; color: var(--text); }
.icon-btn.stop { background: var(--danger); }
.empty { margin: auto; text-align: center; max-width: 520px; padding: 40px 16px; }
.empty h1 { font-size: 28px; } .empty p { color: var(--muted); }
.examples { display: grid; gap: 8px; margin-top: 20px; }
.example { padding: 12px 14px; border-radius: var(--radius); border: 1px solid var(--border);
  background: var(--surface); color: var(--text); cursor: pointer; text-align: left; }
.example:hover { border-color: var(--primary); }
.banner { background: var(--danger); color: #fff; padding: 8px 14px; border-radius: var(--radius-sm); }
.err { color: var(--danger); }
```

- [ ] **Step 5: Run the component tests, confirm pass**; **Step 6: Commit**

```bash
git add frontend/src/components frontend/src/styles/app.css frontend/src/__tests__/components.test.tsx
git commit -m "feat(ui): chat components + styles (bubbles, chips, composer, tables)"
```

---

## Task F6: App wiring + config

**Files:** Create `frontend/src/App.tsx`, `frontend/src/lib/config.ts`; Modify `frontend/src/main.tsx`; Test `frontend/src/__tests__/app.test.tsx`

- [ ] **Step 1: Write `frontend/src/lib/config.ts`**

```ts
export const API_BASE =
  import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
```

- [ ] **Step 2: Write the failing integration test** (mocks `fetch` with a streamed body)

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";

function streamResponse(frames: string[]) {
  const enc = new TextEncoder();
  const body = new ReadableStream({
    start(c) { frames.forEach((f) => c.enqueue(enc.encode(f))); c.close(); },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

beforeEach(() => { localStorage.clear(); });

describe("App", () => {
  it("sends a message and renders the streamed answer", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(streamResponse([
      'event: tool\ndata: {"name":"get_free_agents"}\n\n',
      'event: token\ndata: {"text":"Add "}\n\n',
      'event: token\ndata: {"text":"Josh Hart."}\n\n',
      'event: done\ndata: {}\n\n',
    ]));
    render(<App />);
    await userEvent.type(screen.getByRole("textbox"), "who do I add?");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    expect(await screen.findByText(/Add Josh Hart\./)).toBeInTheDocument();
    expect(screen.getByText(/scanning the waiver wire/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run it, confirm fail**; **Step 4: Implement `frontend/src/App.tsx`**

```tsx
import { useReducer, useRef } from "react";
import { chatReducer, initialState } from "./state/messages";
import { postChatStream } from "./lib/sse";
import { API_BASE } from "./lib/config";
import { useTheme } from "./hooks/useTheme";
import { Header } from "./components/Header";
import { EmptyState } from "./components/EmptyState";
import { MessageBubble } from "./components/MessageBubble";
import { Composer } from "./components/Composer";
import "./styles/tokens.css";
import "./styles/app.css";

export default function App() {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const { theme, toggle } = useTheme();
  const convId = useRef(crypto.randomUUID());
  const abort = useRef<AbortController | null>(null);

  const send = (text: string) => {
    dispatch({ type: "send", text });
    abort.current = new AbortController();
    postChatStream(API_BASE, { message: text, conversation_id: convId.current }, {
      onTool: (name) => dispatch({ type: "tool", name }),
      onToken: (t) => dispatch({ type: "token", text: t }),
      onFinal: (t) => dispatch({ type: "final", text: t }),
      onDone: () => dispatch({ type: "done" }),
      onError: (e) => dispatch({ type: "error", message: String(e) }),
    }, abort.current.signal);
  };
  const stop = () => { abort.current?.abort(); dispatch({ type: "done" }); };

  return (
    <div className="app">
      <Header theme={theme} onToggle={toggle} />
      <div className="list">
        {state.messages.length === 0
          ? <EmptyState onPick={send} />
          : state.messages.map((m, i) => <MessageBubble key={i} m={m} />)}
      </div>
      <Composer streaming={state.streaming} onSend={send} onStop={stop} />
    </div>
  );
}
```

- [ ] **Step 5: Update `frontend/src/main.tsx`** to render `<App/>` (remove the Vite demo). Ensure it imports `./App` and mounts to `#root`.

- [ ] **Step 6: Run the app test, confirm pass**; run the whole frontend suite: `npm test`. **Step 7: Commit**

```bash
git add frontend/src/App.tsx frontend/src/main.tsx frontend/src/lib/config.ts frontend/src/__tests__/app.test.tsx
git commit -m "feat(ui): wire chat app end-to-end over SSE"
```

---

## Task F7: Manual live check (both servers)

- [ ] **Step 1:** Backend (repo root, demo mode + key already in `.env`):
```bash
uv run uvicorn fantasy_gm.api:app --port 8000
```
- [ ] **Step 2:** Frontend (in `frontend/`): `npm run dev` → open the printed localhost URL.
- [ ] **Step 3:** Ask "Who should I pick up this week?" — confirm tool chips animate, the answer streams in, and a stat table renders. Try the dark-mode toggle and an example prompt. Resize to 375px.

---

## Task Q1: Design + accessibility QC (skills)

- [ ] Run the `design:design-critique` skill against the running UI (screenshots of empty state, a full answer with a table, light + dark, mobile width). Apply high-value fixes.
- [ ] Run the `design:accessibility-review` skill (contrast on muted text, focus order, `aria-live` announcement, 44px targets, keyboard-only send). Apply fixes; commit as `fix(ui): address design + a11y review`.

---

## Runbook D1: Deploy (needs your Vercel + Railway/Fly accounts)

> Not automatable from here — these steps require your logins. Do them once.

1. **Backend + Postgres on Railway** (or Fly):
   - New project → add PostgreSQL → copy its `DATABASE_URL`.
   - Deploy the repo as a service; start command:
     `uv run uvicorn fantasy_gm.api:app --host 0.0.0.0 --port $PORT`
   - Set env vars: `DATABASE_URL` (Railway's), `ANTHROPIC_API_KEY`, `BALLDONTLIE_API_KEY`, `DEMO_MODE=true` (until Yahoo approval), `AGENT_MODEL`, `LANGCHAIN_*`, and `FRONTEND_ORIGIN=https://<your-vercel-app>.vercel.app`.
   - After first boot, run once against the prod DB: `run_migrations.py`, `setup_checkpointer.py`, `seed_demo_data.py` (Railway shell or a one-off job).
2. **Frontend on Vercel:**
   - Import the repo, set **Root Directory** = `frontend`, framework preset Vite.
   - Env var `VITE_API_BASE=https://<your-railway-backend-url>`.
   - Deploy → you get the live URL. Put that origin in the backend's `FRONTEND_ORIGIN` and redeploy the backend.
3. **Verify** the live URL end-to-end; add it to the README header and as a repo "Website".

## Runbook D2: Wire the Intent-Analysis loop

1. Confirm the backend runs with `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY` + `LANGCHAIN_PROJECT=fantasy-gm-agent` so every agent run is traced in LangSmith.
2. In the [Intent-Analysis](https://github.com/BarakTal1/Intent-Analysis) app, point its LangSmith ingestion at the `fantasy-gm-agent` project.
3. Define its **skill catalog** as the agent's toolbox (`get_my_roster`, `get_free_agents`, `get_trends`, `get_weekly_schedule`, `get_league_settings`) so skill-gap analysis maps to real capabilities.
4. Use the assistant through the season; capture dashboard screenshots (intent distribution, satisfaction, skill-gap quadrants) for the README once enough real conversations accrue.

## Runbook D3: Swap fixtures → real Yahoo (on approval)

1. When Yahoo approves API access, re-run `scripts/spike_oauth.py` to store a real refresh token, and set your real `YAHOO_LEAGUE_KEY`.
2. Set `DEMO_MODE=false`.
3. Run the agent against real data; verify `client.parse_*` handles the live response shapes (the `# ADJUST`/`# TODO` spots in `client.py`). Fix any nesting differences; the parser unit tests lock the expected shape.
4. Update the README status to "live on real Yahoo data".

---

## Phase 3 Done — Definition of Done

- [ ] Backend: `uv run pytest -v` green (CORS + streaming tests included).
- [ ] Frontend: `npm test` green (useTheme, sse, toolMeta, messages, components, app).
- [ ] Manual live check passes (chips animate, answer streams, table renders, dark mode, 375px).
- [ ] `design-critique` + `accessibility-review` run and high-value fixes applied.
- [ ] Deploy runbook produces a live URL (when you run it); README updated with the link.
- [ ] Intent-Analysis loop wired to the live LangSmith project.
