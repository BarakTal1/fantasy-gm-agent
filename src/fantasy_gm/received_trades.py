"""Received-trades (pending offers) shell.

Turns a list of pending offers other managers sent you into resolved player
objects for the UI. Demo mode reads demo_data/pending_trades.json; on Yahoo API
approval, the live parser in yahoo_client.client supplies the same offer shape.
Direction convention per offer: `they_give` = players offered TO you,
`they_want` = your players they're asking for.
"""


def _resolve(ids: list[str], by_id: dict) -> list[dict]:
    return [by_id[i].model_dump() for i in ids if i in by_id]


def build_offers(offers: list[dict], by_id: dict) -> list[dict]:
    return [{
        "from_team": o["from_team"],
        "date": o["date"],
        "note": o.get("note", ""),
        "they_give": _resolve(o.get("they_give", []), by_id),
        "they_want": _resolve(o.get("they_want", []), by_id),
    } for o in offers]
