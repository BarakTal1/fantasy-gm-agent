from fantasy_gm.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("YAHOO_CLIENT_ID", "cid")
    monkeypatch.setenv("YAHOO_CLIENT_SECRET", "secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    # _env_file=None keeps the test hermetic: ignore any local .env so the
    # assertions reflect process env + defaults only, not the developer's .env.
    s = Settings(_env_file=None)
    assert s.yahoo_client_id == "cid"
    assert s.database_url == "postgresql://x/y"
    assert s.yahoo_redirect_uri == "oob"  # default
