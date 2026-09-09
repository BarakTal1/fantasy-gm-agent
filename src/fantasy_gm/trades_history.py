"""Trade-history demo shell.

Turns a fabricated list of past trades (over players that exist in the demo
league) into per-player before/after stat comparisons. This is a demo bridge:
on Yahoo API approval, replace the `trades` input with real league transactions
and the synthetic `after` map with real post-trade game-log averages.
"""

_SINCE_TRADE_FACTOR = 1.08  # synthetic "form since the trade" bump for the demo


def _sides(ids: list[str], by_id: dict) -> list[dict]:
    out = []
    for i in ids:
        p = by_id.get(i)
        if not p:
            continue
        before = {k: round(float(v), 2) for k, v in p.stats.items()}
        after = {k: round(float(v) * _SINCE_TRADE_FACTOR, 2)
                 for k, v in p.stats.items()}
        out.append({"player_id": p.player_id, "name": p.name,
                    "nba_team": p.nba_team, "before": before, "after": after})
    return out


def build_history(trades: list[dict], by_id: dict) -> list[dict]:
    return [{"date": t["date"], "with_team": t["with_team"],
             "gave": _sides(t.get("gave", []), by_id),
             "got": _sides(t.get("got", []), by_id)} for t in trades]
