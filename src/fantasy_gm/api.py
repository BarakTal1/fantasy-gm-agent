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
            for _node, update in chunk.items():
                msgs = update.get("messages", []) if isinstance(update, dict) else []
                for m in msgs:
                    tool_calls = getattr(m, "tool_calls", None)
                    if tool_calls:
                        for tc in tool_calls:
                            yield _sse("tool", {"name": tc["name"]})
                    elif isinstance(m, AIMessage) and m.content:
                        yield _sse("final", {"text": m.content})

    return StreamingResponse(gen(), media_type="text/event-stream")
