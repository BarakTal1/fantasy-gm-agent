"""Throwaway spike: prove we can count NBA games per team for a date range.

Uses the balldontlie API (https://www.balldontlie.io/) which requires a free
API key. Chosen over free hidden endpoints (NBA CDN, ESPN) because those return
403 to datacenter IPs and would break the nightly sync in cloud deployment.

Requires in .env: BALLDONTLIE_API_KEY
"""
import json
from collections import Counter
from pathlib import Path

import httpx

from fantasy_gm.config import get_settings

URL = "https://api.balldontlie.io/v1/games"
s = get_settings()


def games_for_range(start: str, end: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    cursor: int | None = None
    headers = {"Authorization": s.balldontlie_api_key}
    while True:
        params: dict[str, object] = {
            "start_date": start, "end_date": end, "per_page": 100,
        }
        if cursor is not None:
            params["cursor"] = cursor
        r = httpx.get(URL, params=params, headers=headers, timeout=30)
        if r.status_code >= 400:
            print("Request failed:", r.status_code, r.text[:400])
            r.raise_for_status()
        data = r.json()
        for g in data["data"]:
            counts[g["home_team"]["abbreviation"]] += 1
            counts[g["visitor_team"]["abbreviation"]] += 1
        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break
    return dict(counts)


if __name__ == "__main__":
    if not s.balldontlie_api_key:
        raise SystemExit("Set BALLDONTLIE_API_KEY in .env first "
                         "(free key from https://www.balldontlie.io/).")
    # Pick a real Mon–Sun fantasy week within the current season.
    counts = games_for_range("2025-01-06", "2025-01-12")
    Path("tests/fixtures").mkdir(parents=True, exist_ok=True)
    Path("tests/fixtures/schedule_week.json").write_text(json.dumps(counts, indent=2))
    print("games per team this week:", counts)
    print("saved tests/fixtures/schedule_week.json")
