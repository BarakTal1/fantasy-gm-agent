from datetime import UTC, datetime, timedelta

import httpx

from fantasy_gm.config import get_settings
from fantasy_gm.db import execute, fetch_one

TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
_SKEW = timedelta(seconds=60)  # refresh a bit early


def _save(access: str, refresh: str, expires_at: datetime) -> None:
    execute(
        "INSERT INTO oauth_tokens (id, access_token, refresh_token, expires_at) "
        "VALUES (1, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET "
        "access_token=EXCLUDED.access_token, refresh_token=EXCLUDED.refresh_token, "
        "expires_at=EXCLUDED.expires_at",
        (access, refresh, expires_at),
    )


def _refresh(refresh_token: str) -> str:
    s = get_settings()
    resp = httpx.post(TOKEN_URL, data={
        "client_id": s.yahoo_client_id,
        "client_secret": s.yahoo_client_secret,
        "redirect_uri": s.yahoo_redirect_uri,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    })
    if resp.status_code >= 400:
        resp.raise_for_status()
    body = resp.json()
    expires_at = datetime.now(UTC) + timedelta(seconds=body["expires_in"])
    new_refresh = body.get("refresh_token", refresh_token)
    _save(body["access_token"], new_refresh, expires_at)
    return body["access_token"]


def get_access_token() -> str:
    row = fetch_one(
        "SELECT access_token, refresh_token, expires_at FROM oauth_tokens WHERE id=1")
    if row is None:
        raise RuntimeError("No Yahoo tokens stored. Run scripts/spike_oauth.py first.")
    if row["expires_at"] - _SKEW > datetime.now(UTC):
        return row["access_token"]
    return _refresh(row["refresh_token"])
