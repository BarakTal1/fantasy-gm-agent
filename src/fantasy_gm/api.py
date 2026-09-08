import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from pydantic import BaseModel

from fantasy_gm.agent import build_agent
from fantasy_gm.config import get_settings
from fantasy_gm.schemas import LeagueSettings
from fantasy_gm.tools import get_league_settings

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


app = FastAPI(title="Fantasy GM Agent", lifespan=lifespan)

_ALLOWED_ORIGINS = [
    "http://localhost:5173",   # Vite dev
    "http://127.0.0.1:5173",
]
# In production, add the deployed frontend origin via env (see deploy runbook).
if os.getenv("FRONTEND_ORIGIN"):
    _ALLOWED_ORIGINS.append(os.environ["FRONTEND_ORIGIN"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single-user demo config — replace with real values / auth in a multi-user build.
LEAGUE_KEY = "428.l.123456"
MY_TEAM_KEY = "428.l.123456.t.1"


class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"


def _load_league() -> LeagueSettings:
    return get_league_settings(LEAGUE_KEY)


def _make_model():
    s = get_settings()
    return ChatAnthropic(model=s.agent_model, api_key=s.anthropic_api_key,
                         max_tokens=4096)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content
                   if isinstance(b, dict) and b.get("type") == "text")


def _chunk_text(msg) -> str:
    """Text delta from a streamed message chunk (Opus 5 returns block lists)."""
    return _text(getattr(msg, "content", "") or "")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    agent = build_agent(league=_load_league(), league_key=LEAGUE_KEY,
                        my_team_key=MY_TEAM_KEY, model=_make_model(),
                        checkpointer=_checkpointer)

    def gen():
        config = {"configurable": {"thread_id": req.conversation_id}}
        emitted_token = False
        last_id = None
        for mode, chunk in agent.stream(
            {"messages": [HumanMessage(req.message)]},
            config=config,
            stream_mode=["updates", "messages"],
        ):
            if mode == "messages":
                msg, _meta = chunk
                # Only stream assistant text — messages mode also surfaces
                # ToolMessages (raw JSON tool results), which must NOT leak
                # into the answer. AIMessageChunk is a subclass of AIMessage.
                tool_calls = getattr(msg, "tool_calls", None)
                if isinstance(msg, AIMessage) and not tool_calls:
                    text = _chunk_text(msg)
                    if text:
                        # Separate distinct assistant turns (preamble vs final
                        # answer) so markdown blocks don't glue together.
                        mid = getattr(msg, "id", None)
                        if emitted_token and mid != last_id:
                            yield _sse("token", {"text": "\n\n"})
                        last_id = mid
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

    return StreamingResponse(gen(), media_type="text/event-stream")
