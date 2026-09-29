"""Throwaway spike: prove Yahoo OAuth2 + pull real fantasy data, save fixtures.

Flow (real redirect, no local server needed):
  1. Script prints an authorize URL and opens it in your browser.
  2. You approve access. Yahoo redirects your browser to
     https://localhost:8000/callback?code=XXXXX  (the page WON'T load — that's fine).
  3. Copy the value of `code=` from the browser address bar, paste it here.
  4. Script exchanges the code for tokens and saves real API responses as fixtures.

Requires in .env: YAHOO_CLIENT_ID, YAHOO_CLIENT_SECRET,
                   YAHOO_REDIRECT_URI=https://localhost:8000/callback
"""
import json
import sys
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fantasy_gm.config import get_settings  # noqa: E402

AUTH = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN = "https://api.login.yahoo.com/oauth2/get_token"
API = "https://fantasysports.yahooapis.com/fantasy/v2"
s = get_settings()
FIX = Path("tests/fixtures")


def get_tokens() -> dict:
    params = {
        "client_id": s.yahoo_client_id,
        "redirect_uri": s.yahoo_redirect_uri,
        "response_type": "code",
    }
    url = f"{AUTH}?{urlencode(params)}"
    print("\n1) Opening this URL in your browser (approve access):\n", url, "\n")
    webbrowser.open(url)
    print("2) After approving, your browser goes to a localhost URL that won't load.")
    print("   Copy the `code=...` value from the address bar and paste it below.\n")
    code = input("code: ").strip()
    r = httpx.post(TOKEN, data={
        "client_id": s.yahoo_client_id,
        "client_secret": s.yahoo_client_secret,
        "redirect_uri": s.yahoo_redirect_uri,
        "code": code,
        "grant_type": "authorization_code",
    })
    if r.status_code >= 400:
        print("Token exchange failed:", r.status_code, r.text)
        r.raise_for_status()
    return r.json()


def pull(access_token: str, path: str) -> dict:
    r = httpx.get(f"{API}/{path}?format=json",
                  headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
    if r.status_code >= 400:
        print(f"GET {path} failed:", r.status_code, r.text[:500])
        r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    FIX.mkdir(parents=True, exist_ok=True)
    tokens = get_tokens()
    print("\n=== SAVE THIS REFRESH TOKEN (needed later) ===")
    print(tokens["refresh_token"])
    print("=" * 46, "\n")
    at = tokens["access_token"]

    # 1) Discover your NBA leagues, save the payload, and find your league_key.
    leagues = pull(at, "users;use_login=1/games;game_keys=nba/leagues")
    (FIX / "leagues.json").write_text(json.dumps(leagues, indent=2))
    print("Saved tests/fixtures/leagues.json")
    print("Open it and find your league_key (looks like '428.l.12345'),")
    print("then set YAHOO_LEAGUE_KEY in .env.\n")

    lk = s.yahoo_league_key or input("paste league_key now (e.g. 428.l.12345): ").strip()

    (FIX / "league_settings.json").write_text(
        json.dumps(pull(at, f"league/{lk}/settings"), indent=2))
    print("Saved league_settings.json")

    (FIX / "roster.json").write_text(
        json.dumps(pull(at, f"league/{lk}/teams;out=roster,stats"), indent=2))
    print("Saved roster.json")

    (FIX / "free_agents.json").write_text(
        json.dumps(pull(at, f"league/{lk}/players;status=FA;out=stats"), indent=2))
    print("Saved free_agents.json")

    print("\nDone. Inspect the three fixture files, then tell your assistant.")
