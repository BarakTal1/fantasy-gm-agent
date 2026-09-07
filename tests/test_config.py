from fantasy_gm.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("YAHOO_CLIENT_ID", "cid")
    monkeypatch.setenv("YAHOO_CLIENT_SECRET", "secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    s = Settings()
    assert s.yahoo_client_id == "cid"
    assert s.database_url == "postgresql://x/y"
    assert s.yahoo_redirect_uri == "oob"  # default
