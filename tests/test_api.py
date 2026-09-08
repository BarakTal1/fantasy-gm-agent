from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage


def test_dashboard_endpoint_returns_all_sections(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import LeagueSettings, Player, Team
    monkeypatch.setattr(api, "_load_league",
        lambda: LeagueSettings(league_key="428.l.123456", format="category",
                               categories=["PTS", "AST"]))
    monkeypatch.setattr(api, "_all_teams",
        lambda: [Team(team_key="428.l.123456.t.1", name="My Squad",
                      players=[Player(player_id="1", name="A", nba_team="LAL",
                                      stats={"PTS": 20, "AST": 5})])])
    monkeypatch.setattr(api, "_free_agents",
        lambda: [Player(player_id="9", name="FA", nba_team="LAL", stats={"PTS": 10})])
    monkeypatch.setattr(api, "_trends_for", lambda ids: {"9": {"PTS": 11.0}})
    monkeypatch.setattr(api, "_week_games", lambda: {"LAL": 4})
    from fastapi.testclient import TestClient
    body = TestClient(api.app).get("/analytics/dashboard").json()
    assert set(body) == {"format", "category_profile", "streaming_board",
                         "buy_low_sell_high", "schedule", "recommended_pickups"}
    assert body["format"] == "category"
    assert body["category_profile"]["PTS"]["you"] == 20


def test_trade_analyze_returns_deltas_and_verdict(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import LeagueSettings, Player
    pool = {"1": Player(player_id="1", name="Mine", nba_team="LAL", stats={"AST": 8}),
            "2": Player(player_id="2", name="Theirs", nba_team="BOS", stats={"AST": 2})}
    monkeypatch.setattr(api, "_load_league",
        lambda: LeagueSettings(league_key="428.l.123456", format="category",
                               categories=["AST"]))
    monkeypatch.setattr(api, "_players_by_id", lambda ids: {i: pool[i] for i in ids})
    monkeypatch.setattr(api, "_verdict",
                        lambda delta, summary, give, get: "Decline — you lose assists.")
    from fastapi.testclient import TestClient
    r = TestClient(api.app).post("/trade/analyze",
                                 json={"give": ["1"], "get": ["2"]})
    body = r.json()
    assert body["format"] == "category"
    assert body["delta"]["AST"] == -6.0
    assert "assists" in body["verdict"].lower()
    assert body["summary"]["worsened"] == ["AST"]


def test_league_teams_endpoint(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import Player, Team
    monkeypatch.setattr(api, "_all_teams", lambda: [
        Team(team_key="428.l.1.t.1", name="Mine",
             players=[Player(player_id="1", name="A", nba_team="LAL", stats={"PTS": 20})])])
    from fastapi.testclient import TestClient
    body = TestClient(api.app).get("/league/teams").json()
    assert body["my_team_key"] == api.MY_TEAM_KEY
    assert body["teams"][0]["players"][0]["name"] == "A"


def test_dashboard_is_format_tagged(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import LeagueSettings, Player, Team
    monkeypatch.setattr(api, "_load_league",
        lambda: LeagueSettings(league_key="k", format="points",
                               point_weights={"PTS": 1.0}))
    monkeypatch.setattr(api, "_all_teams", lambda: [
        Team(team_key=api.MY_TEAM_KEY, name="Mine",
             players=[Player(player_id="1", name="A", nba_team="LAL", stats={"PTS": 20})])])
    monkeypatch.setattr(api, "_free_agents", lambda: [
        Player(player_id="9", name="FA", nba_team="LAL", stats={"PTS": 15})])
    monkeypatch.setattr(api, "_trends_for", lambda ids: {})
    monkeypatch.setattr(api, "_week_games", lambda: {"LAL": 4})
    from fastapi.testclient import TestClient
    body = TestClient(api.app).get("/analytics/dashboard").json()
    assert body["format"] == "points"
    assert "points_value_board" in body            # points view, not radar


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


def test_chat_threads_conversation_id(monkeypatch):
    from langchain_core.messages import AIMessage

    from fantasy_gm import api
    from fantasy_gm.schemas import LeagueSettings
    from tests.support.fake_chat import FakeToolCallingModel

    captured = {}

    class SpyAgent:
        def stream(self, inputs, config=None, stream_mode=None):
            captured["config"] = config
            return iter([("updates", {"agent": {"messages": [AIMessage(content="ok")]}})])

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


def test_cors_headers_present():
    from fastapi.testclient import TestClient

    from fantasy_gm import api
    r = TestClient(api.app).options(
        "/chat",
        headers={"Origin": "http://localhost:5173",
                 "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin") in {"*", "http://localhost:5173"}


def test_chat_passes_checkpointer(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import LeagueSettings
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
