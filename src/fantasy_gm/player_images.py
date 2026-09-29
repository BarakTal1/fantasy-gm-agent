"""Player headshot resolver.

A committed table (demo_data/player_images.json) maps player_id -> headshot URL;
it's generated from the demo roster/FA ids (see scripts/gen_player_images.py)
using the official NBA CDN pattern. For any id missing from the table we derive
the same CDN URL when the id is an NBA person-id (all digits); otherwise return
None and let the UI fall back to an initials avatar. On live Yahoo data the
image comes from Yahoo's own player metadata instead (see yahoo_client.client).
"""
import json
from functools import cache
from pathlib import Path

_DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo_data"
_CDN = "https://cdn.nba.com/headshots/nba/latest/260x190/{id}.png"


@cache
def _load_table() -> dict[str, str]:
    path = _DEMO_DIR / "player_images.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


# Module-level handle so tests can monkeypatch a table in place.
_TABLE = _load_table()


def resolve_image(player_id: str) -> str | None:
    if player_id in _TABLE:
        return _TABLE[player_id]
    if player_id.isdigit():
        return _CDN.format(id=player_id)
    return None
