"""Deterministic suggested-trades generator.

Scans the league for packages the user could OFFER other teams: target their
buy-low players who fill the user's weak categories, give up the user's
sell-high / roster players, keep the value gap within a fairness tolerance so
the other side might plausibly accept, and rank by need-weighted fit. No Claude
at generation time — the frontend's Analyze button runs the existing verdict
engine on demand for a chosen proposal.
"""
import itertools

from fantasy_gm import scoring, trade
from fantasy_gm.analytics import _need_weights, buy_low_sell_high
from fantasy_gm.schemas import LeagueSettings, Player, Team

DEFAULT_LIMIT = 8
WEAK_EPS = 0.05        # need-weight above 1+this counts as a "weak" category
PKG_POOL = 6           # cap players considered per side before combining (bounds combos)
FAIRNESS_PCT = 0.25    # |value gap| must be within this fraction of the larger side
MIN_NEED_FIT = 0.01    # drop proposals that don't actually help a weak category


def _value(players: list[Player], settings: LeagueSettings) -> float:
    return sum(scoring.player_value(p, settings) for p in players)


def _weak_cats(weights: dict[str, float], cats: list[str]) -> list[str]:
    return [c for c in cats if not c.endswith("%")
            and c not in scoring.NEGATIVE_CATS and weights.get(c, 1.0) > 1 + WEAK_EPS]


def _need_fit(give: list[Player], get: list[Player],
              weights: dict[str, float], cats: list[str]) -> tuple[float, dict]:
    """Need-weighted positive improvement to my categories from the swap.

    Returns (fit, delta) so the caller can reuse the same category_delta for
    targeted_categories instead of recomputing it (they must never diverge)."""
    delta = trade.category_delta(give, get, cats)   # get - give, per cat
    fit = 0.0
    for c in cats:
        if c.endswith("%"):
            continue
        gain = -delta[c] if c in scoring.NEGATIVE_CATS else delta[c]
        if gain > 0:
            fit += gain * weights.get(c, 1.0)
    return fit, delta


def _candidate_packages(assets: list[Player], targets: list[Player],
                        settings: LeagueSettings) -> list[tuple[list[Player], list[Player]]]:
    """Unfiltered give/get candidates (1-for-1, 2-for-1, 1-for-2) — callers
    still apply need-fit and fairness filters before treating these as
    final proposals."""
    assets = sorted(assets, key=lambda p: scoring.player_value(p, settings),
                    reverse=True)[:PKG_POOL]
    targets = sorted(targets, key=lambda p: scoring.player_value(p, settings),
                     reverse=True)[:PKG_POOL]
    out: list[tuple[list[Player], list[Player]]] = []
    for a in assets:
        for t in targets:
            out.append(([a], [t]))                              # 1-for-1
    for combo in itertools.combinations(assets, 2):
        for t in targets:
            out.append((list(combo), [t]))                      # 2-for-1
    for a in assets:
        for combo in itertools.combinations(targets, 2):
            out.append(([a], list(combo)))                      # 1-for-2
    return out


def _suggest_category(my_team: Team, all_teams: list[Team], trends: dict,
                      settings: LeagueSettings, limit: int) -> list[dict]:
    cats = settings.categories
    weights = _need_weights(my_team, all_teams, cats)
    weak = _weak_cats(weights, cats)
    # My tradeable assets: sell-high flagged players; fall back to the whole
    # roster when nothing is flagged, so a proposal is still possible.
    my_signals = {r["player_id"]: r for r in buy_low_sell_high(my_team.players, trends, cats)}
    assets = [p for p in my_team.players
              if my_signals.get(p.player_id, {}).get("signal") == "sell_high"]
    if not assets:
        assets = list(my_team.players)

    proposals_out: list[dict] = []
    # Dedupe key. The three candidate shapes (1-1, 2-1, 1-2) currently have
    # distinct give/get sizes so they can never collide in practice — this
    # guards against a future package shape overlapping an existing one.
    seen: set[tuple] = set()
    for team in all_teams:
        if team.team_key == my_team.team_key:
            continue
        their_signals = {r["player_id"]: r
                         for r in buy_low_sell_high(team.players, trends, cats)}
        targets = [p for p in team.players
                   if their_signals.get(p.player_id, {}).get("signal") == "buy_low"
                   and (not weak or sum(p.stat(c) for c in weak) > 0)]
        for give, get in _candidate_packages(assets, targets, settings):
            key = (team.team_key,
                   tuple(sorted(p.player_id for p in give)),
                   tuple(sorted(p.player_id for p in get)))
            if key in seen:
                continue
            fit, delta = _need_fit(give, get, weights, cats)
            if fit < MIN_NEED_FIT:
                continue
            gv, tv = _value(give, settings), _value(get, settings)
            gap = abs(gv - tv)
            tol = max(gv, tv, 1.0) * FAIRNESS_PCT
            if gap > tol:
                continue
            seen.add(key)
            targeted = [c for c in weak
                        if (delta[c] > 0 if c not in scoring.NEGATIVE_CATS
                            else delta[c] < 0)]
            proposals_out.append({
                "with_team": team.name,
                "give": [p.model_dump() for p in give],
                "get": [p.model_dump() for p in get],
                "targeted_categories": targeted,
                "fairness_gap": round(gap, 2),
                "need_fit": round(fit, 2),
            })
    proposals_out.sort(key=lambda x: x["need_fit"], reverse=True)
    return proposals_out[:limit]


def suggest_trades(my_team: Team, all_teams: list[Team], trends: dict,
                   settings: LeagueSettings, limit: int = DEFAULT_LIMIT) -> list[dict]:
    if settings.is_points:
        from fantasy_gm.proposals_points import suggest_points   # built in Task 3
        return suggest_points(my_team, all_teams, trends, settings, limit)
    return _suggest_category(my_team, all_teams, trends, settings, limit)
