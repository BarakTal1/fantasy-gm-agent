from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage


def _mk_category(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import LeagueSettings, Player, Team
    monkeypatch.setattr(api, "_league_for",
        lambda request: LeagueSettings(league_key="428.l.123456", format="category",
                                       categories=["PTS", "AST"]))
    monkeypatch.setattr(api, "_all_teams",
        lambda: [Team(team_key=api.MY_TEAM_KEY, name="My Squad",
                      players=[Player(player_id="1", name="A", nba_team="LAL",
                                      stats={"PTS": 20, "AST": 5})]),
                 Team(team_key="428.l.123456.t.2", name="Rival",
                      players=[Player(player_id="2", name="B", nba_team="BOS",
                                      stats={"PTS": 10, "AST": 9})])])
    monkeypatch.setattr(api, "_free_agents",
        lambda: [Player(player_id="9", name="FA", nba_team="LAL", stats={"PTS": 10})])
    monkeypatch.setattr(api, "_trends_for", lambda ids: {"9": {"PTS": 11.0}})
    monkeypatch.setattr(api, "_week_games", lambda: {"LAL": 4})


def test_my_team_analytics_category(monkeypatch):
    from fantasy_gm import api
    _mk_category(monkeypatch)
    body = TestClient(api.app).get("/analytics/my-team").json()
    assert body["format"] == "category"
    assert body["category_profile"]["PTS"]["you"] == 20
    assert body["roster"][0]["form"] in {"buy_low", "sell_high", "neutral"}
    assert "games" in body["roster"][0]
    assert "weekdays" not in body            # weekdays moved to /analytics/waivers


def test_waivers_analytics_category(monkeypatch):
    from fantasy_gm import api
    _mk_category(monkeypatch)
    body = TestClient(api.app).get("/analytics/waivers").json()
    assert body["format"] == "category"
    assert "recommended_pickups" in body and "streaming_board" in body


def test_league_analytics_category(monkeypatch):
    from fantasy_gm import api
    _mk_category(monkeypatch)
    body = TestClient(api.app).get("/analytics/league").json()
    assert body["format"] == "category"
    assert "category_profile" in body and "teams" in body
    assert isinstance(body["buy_low_sell_high"], list)


def test_dashboard_endpoint_removed():
    from fantasy_gm import api
    assert TestClient(api.app).get("/analytics/dashboard").status_code == 404


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


def test_league_info_endpoint(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import LeagueSettings
    monkeypatch.setattr(api, "_league_info",
                        lambda: LeagueSettings(league_key="k", format="points",
                                               name="My Real League"))
    from fastapi.testclient import TestClient
    body = TestClient(api.app).get("/league/info").json()
    assert body == {"name": "My Real League", "format": "points",
                    "format_label": "Points"}


def test_chat_rate_limited(monkeypatch):
    from langchain_core.messages import AIMessage

    from fantasy_gm import api
    from fantasy_gm.ratelimit import RateLimiter
    from fantasy_gm.schemas import LeagueSettings
    monkeypatch.setattr(api, "_claude_limiter",
                        RateLimiter(max_requests=1, window_seconds=60))
    monkeypatch.setattr(api, "_load_league",
                        lambda: LeagueSettings(league_key="k", format="category"))
    monkeypatch.setattr(api, "_make_model", lambda: object())

    class SpyAgent:
        def stream(self, *a, **k):
            return iter([("updates", {"agent": {"messages": [AIMessage(content="ok")]}})])
    monkeypatch.setattr(api, "build_agent", lambda **kw: SpyAgent())

    from fastapi.testclient import TestClient
    c = TestClient(api.app)
    r1 = c.post("/chat", json={"message": "hi", "conversation_id": "a"})
    r2 = c.post("/chat", json={"message": "hi", "conversation_id": "a"})
    assert r1.status_code == 200
    assert r2.status_code == 429


def test_auth_register_login_me(db):
    from fantasy_gm import api
    c = TestClient(api.app)
    r = c.post("/auth/register", json={"email": "x@y.com", "password": "pw"})
    assert r.status_code == 200 and r.json()["email"] == "x@y.com"
    assert c.get("/auth/me").json()["email"] == "x@y.com"   # cookie persists
    dup = c.post("/auth/register", json={"email": "x@y.com", "password": "pw"})
    assert dup.status_code == 409
    c.post("/auth/logout")
    assert c.get("/auth/me").status_code == 401
    bad = c.post("/auth/login", json={"email": "x@y.com", "password": "nope"})
    assert bad.status_code == 401
    ok = c.post("/auth/login", json={"email": "x@y.com", "password": "pw"})
    assert ok.status_code == 200


def test_settings_patch_updates_format(db):
    from fantasy_gm import api
    c = TestClient(api.app)
    c.post("/auth/register", json={"email": "s@s.com", "password": "pw"})
    r = c.patch("/settings", json={"league_format": "points"})
    assert r.status_code == 200 and r.json()["league_format"] == "points"
    assert c.get("/auth/me").json()["league_format"] == "points"
    bad = c.patch("/settings", json={"league_format": "bogus"})
    assert bad.status_code == 400


def test_settings_patch_requires_auth(db):
    from fantasy_gm import api
    r = TestClient(api.app).patch("/settings", json={"league_format": "points"})
    assert r.status_code == 401


def test_trade_history_endpoint(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import Player, Team
    monkeypatch.setattr(api, "_all_teams", lambda: [
        Team(team_key=api.MY_TEAM_KEY, name="Mine",
             players=[Player(player_id="1628368", name="Fox", nba_team="SAS",
                             stats={"PTS": 25.0})])])
    monkeypatch.setattr(api, "_free_agents", lambda: [
        Player(player_id="1629628", name="Barrett", nba_team="TOR",
               stats={"PTS": 20.0})])
    body = TestClient(api.app).get("/trades/history").json()
    assert len(body["trades"]) >= 1
    t0 = body["trades"][0]                 # fixture: gave Barrett, got Fox
    assert t0["got"][0]["name"] == "Fox"
    assert t0["got"][0]["after"]["PTS"] > t0["got"][0]["before"]["PTS"]


def test_received_trades_endpoint(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import Player, Team
    monkeypatch.setattr(api, "_all_teams", lambda: [
        Team(team_key=api.MY_TEAM_KEY, name="Mine",
             players=[Player(player_id="1626164", name="Booker", nba_team="PHX",
                             stats={"PTS": 27.0})])])
    monkeypatch.setattr(api, "_free_agents", lambda: [
        Player(player_id="202681", name="Kyrie", nba_team="DAL", stats={"PTS": 24.0})])
    monkeypatch.setattr(api, "_pending_offers", lambda: [
        {"from_team": "Team 2", "date": "2026-01-20", "note": "swap",
         "they_give": ["202681"], "they_want": ["1626164"]}])
    body = TestClient(api.app).get("/trades/received").json()
    assert len(body["offers"]) == 1
    assert body["offers"][0]["they_give"][0]["name"] == "Kyrie"
    assert body["offers"][0]["they_want"][0]["name"] == "Booker"


def test_suggestions_endpoint(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import LeagueSettings, Player, Team
    monkeypatch.setattr(api, "_league_for",
        lambda request: LeagueSettings(league_key="k", format="category",
                                       categories=["PTS", "AST"]))
    monkeypatch.setattr(api, "_all_teams", lambda: [
        Team(team_key=api.MY_TEAM_KEY, name="Mine",
             players=[Player(player_id="m1", name="Scorer", nba_team="LAL",
                             stats={"PTS": 20, "AST": 2}),
                      Player(player_id="m2", name="Role", nba_team="LAL",
                             stats={"PTS": 12, "AST": 3})]),
        Team(team_key="428.l.123456.t.2", name="Rival",
             players=[Player(player_id="r1", name="Dimer", nba_team="BOS",
                             stats={"PTS": 6, "AST": 11})])])
    monkeypatch.setattr(api, "_trends_for",
        lambda ids: {"r1": {"PTS": 3, "AST": 5}})   # rival dimer cold -> buy_low
    body = TestClient(api.app).get("/trades/suggestions").json()
    assert body["format"] == "category"
    assert isinstance(body["suggestions"], list)
    assert body["suggestions"] and body["suggestions"][0]["with_team"] == "Rival"
