from datetime import UTC, datetime, timedelta

import httpx

from fantasy_gm.yahoo_client import auth


def _save(access, refresh, expires_at):
    from fantasy_gm.db import execute
    execute(
        "INSERT INTO oauth_tokens (id, access_token, refresh_token, expires_at) "
        "VALUES (1, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET "
        "access_token=EXCLUDED.access_token, refresh_token=EXCLUDED.refresh_token, "
        "expires_at=EXCLUDED.expires_at",
        (access, refresh, expires_at),
    )


def test_returns_valid_token_without_refresh(db):
    future = datetime.now(UTC) + timedelta(minutes=30)
    _save("good", "r", future)
    assert auth.get_access_token() == "good"


def test_refreshes_when_expired(db, monkeypatch):
    past = datetime.now(UTC) - timedelta(minutes=1)
    _save("stale", "r-token", past)

    def fake_post(url, data=None, **kw):
        assert data["grant_type"] == "refresh_token"
        assert data["refresh_token"] == "r-token"
        return httpx.Response(200, json={
            "access_token": "fresh", "refresh_token": "r-token2",
            "expires_in": 3600})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert auth.get_access_token() == "fresh"
    # persisted for next time
    assert auth.get_access_token() == "fresh"
