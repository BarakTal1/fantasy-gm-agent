import { useEffect, useState } from "react";
import {
  analyzeTrade, getTeams, type Team,
  getReceivedTrades, getTradeSuggestions, type ReceivedOffer, type TradeSuggestion,
} from "../lib/api";
import { PlayerPicker } from "../components/PlayerPicker";
import { ErrorBanner } from "../components/ErrorBanner";
import { AnalyzeTrade } from "../components/AnalyzeTrade";
import { TradeHistoryView } from "./TradeHistoryView";

interface CategoryTradeResult {
  format: "category";
  delta: Record<string, number>;
  summary: { improved: string[]; worsened: string[] };
  verdict: string;
  recommendation: "ACCEPT" | "DECLINE" | "COUNTER";
}

interface PointsTradeResult {
  format: "points";
  delta: { give_value: number; get_value: number; net: number };
  verdict: string;
  recommendation: "ACCEPT" | "DECLINE" | "COUNTER";
}

type TradeResult = CategoryTradeResult | PointsTradeResult;

/** Strip the trailing ACCEPT/DECLINE/COUNTER keyword the backend appends to the verdict,
 * since the recommendation badge already surfaces it — avoids showing it twice. */
function narrativeOnly(verdict: string, recommendation: string): string {
  return verdict.replace(new RegExp(`\\s*${recommendation}\\.?\\s*$`), "").trim();
}

export function TradeView() {
  const [teams, setTeams] = useState<Team[] | null>(null);
  const [myTeamKey, setMyTeamKey] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [opponentKey, setOpponentKey] = useState<string>("");
  const [give, setGive] = useState<string[]>([]);
  const [get, setGet] = useState<string[]>([]);

  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [result, setResult] = useState<TradeResult | null>(null);

  const [offers, setOffers] = useState<ReceivedOffer[]>([]);
  const [suggestions, setSuggestions] = useState<TradeSuggestion[]>([]);

  useEffect(() => {
    getReceivedTrades().then((d) => setOffers(d.offers)).catch(() => setOffers([]));
    getTradeSuggestions().then((d) => setSuggestions(d.suggestions)).catch(() => setSuggestions([]));
  }, []);

  const loadTeams = () => {
    setLoadError(null);
    setTeams(null);
    getTeams()
      .then((d) => {
        setTeams(d.teams);
        setMyTeamKey(d.my_team_key);
        const firstOpponent = d.teams.find((t) => t.team_key !== d.my_team_key);
        setOpponentKey(firstOpponent ? firstOpponent.team_key : "");
      })
      .catch((e) => setLoadError(String(e)));
  };

  useEffect(loadTeams, []);

  if (loadError) {
    return <ErrorBanner message={`Failed to load rosters: ${loadError}`} onRetry={loadTeams} />;
  }
  if (!teams || myTeamKey === null) {
    return (
      <div className="trade" aria-busy="true" aria-live="polite">
        <span className="sr-table">Loading rosters…</span>
        <div className="skeleton skeleton-row" />
        <div className="skeleton skeleton-row" />
        <div className="skeleton skeleton-block" />
      </div>
    );
  }

  const myTeam = teams.find((t) => t.team_key === myTeamKey) ?? teams[0];
  const opponentTeams = teams.filter((t) => t.team_key !== myTeamKey);
  const opponent = teams.find((t) => t.team_key === opponentKey);

  const toggleGive = (id: string) =>
    setGive((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  const toggleGet = (id: string) =>
    setGet((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const giveNames = myTeam.players.filter((p) => give.includes(p.player_id));
  const getNames = (opponent?.players ?? []).filter((p) => get.includes(p.player_id));

  const analyze = async () => {
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      const r = await analyzeTrade(give, get);
      setResult(r);
    } catch (e) {
      setAnalyzeError(String(e));
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="trade">
      <section className="trade-section">
        <h2>Trade offers received</h2>
        {offers.length === 0 && <div className="empty">No offers right now.</div>}
        {offers.map((o, i) => (
          <div key={`${o.from_team}-${i}`} className="offer-card">
            <div className="offer-head"><strong>{o.from_team}</strong> <em>{o.date}</em></div>
            {o.note && <p className="offer-note">{o.note}</p>}
            <div className="offer-sides">
              <div><span className="side-label">They give</span>
                {o.they_give.map((p) => <span key={p.player_id} className="selected-card get">{p.name}</span>)}</div>
              <div><span className="side-label">They want</span>
                {o.they_want.map((p) => <span key={p.player_id} className="selected-card give">{p.name}</span>)}</div>
            </div>
            <AnalyzeTrade give={o.they_want.map((p) => p.player_id)}
                          get={o.they_give.map((p) => p.player_id)} />
          </div>
        ))}
      </section>

      <section className="trade-section">
        <h2>Suggested trades to propose</h2>
        {suggestions.length === 0 && <div className="empty">No strong suggestions this week.</div>}
        {suggestions.map((s, i) => (
          <div key={`${s.with_team}-${i}`} className="offer-card">
            <div className="offer-head"><strong>{s.with_team}</strong></div>
            <div className="offer-sides">
              <div><span className="side-label">You give</span>
                {s.give.map((p) => <span key={p.player_id} className="selected-card give">{p.name}</span>)}</div>
              <div><span className="side-label">You get</span>
                {s.get.map((p) => <span key={p.player_id} className="selected-card get">{p.name}</span>)}</div>
            </div>
            {s.targeted_categories.length > 0 && (
              <p className="offer-note">Targets: {s.targeted_categories.join(", ")} · fairness gap {s.fairness_gap}</p>
            )}
            <AnalyzeTrade give={s.give.map((p) => p.player_id)}
                          get={s.get.map((p) => p.player_id)} />
          </div>
        ))}
      </section>

      <div className="trade-pickers">
        <PlayerPicker label="Your roster (give)" players={myTeam.players}
          selected={give} onToggle={toggleGive} />

        <div className="opponent-select">
          <label htmlFor="opponent-select">Opponent team</label>
          <select
            id="opponent-select"
            aria-label="opponent team"
            value={opponentKey}
            onChange={(e) => { setOpponentKey(e.target.value); setGet([]); }}
          >
            {opponentTeams.map((t) => (
              <option key={t.team_key} value={t.team_key}>{t.name}</option>
            ))}
          </select>
        </div>

        <PlayerPicker label="Their roster (get)" players={opponent?.players ?? []}
          selected={get} onToggle={toggleGet} />
      </div>

      {(giveNames.length > 0 || getNames.length > 0) && (
        <div className="selected-cards">
          {giveNames.map((p) => <span key={p.player_id} className="selected-card give">{p.name}</span>)}
          {getNames.map((p) => <span key={p.player_id} className="selected-card get">{p.name}</span>)}
        </div>
      )}

      <button
        type="button"
        className="analyze-btn"
        disabled={analyzing || give.length === 0 || get.length === 0}
        onClick={analyze}
      >
        {analyzing ? "Analyzing…" : "Analyze"}
      </button>

      {analyzeError && (
        <ErrorBanner message={`Failed to analyze trade: ${analyzeError}`} onRetry={analyze} />
      )}

      {!result && !analyzeError && (
        <div className="empty">Pick players to analyze.</div>
      )}

      {result && result.format === "category" && (
        <div className="trade-result">
          <div className={`verdict-card rec-${result.recommendation.toLowerCase()}`}>
            <span className="badge">{result.recommendation}</span>
            <p>{narrativeOnly(result.verdict, result.recommendation)}</p>
          </div>

          <table className="delta-table">
            <caption>Per-category net change</caption>
            <thead><tr><th>Category</th><th>Change</th></tr></thead>
            <tbody>
              {Object.entries(result.delta).map(([cat, v]) => {
                const good = result.summary.improved.includes(cat);
                const bad = result.summary.worsened.includes(cat);
                const cls = good ? "good" : bad ? "bad" : "neutral";
                const label = good ? "improved" : bad ? "worsened" : "unchanged";
                return (
                  <tr key={cat} className={cls}>
                    <td>{cat}{cat === "TO" && <em> (lower is better)</em>}</td>
                    <td>{v > 0 ? `+${v}` : v} <span className="delta-label">({label})</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {result && result.format === "points" && (
        <div className="trade-result">
          <div className={`verdict-card rec-${result.recommendation.toLowerCase()}`}>
            <span className="badge">{result.recommendation}</span>
            <p>{narrativeOnly(result.verdict, result.recommendation)}</p>
          </div>

          <table className="delta-table">
            <caption>Fantasy points value</caption>
            <thead><tr><th>Give</th><th>Get</th><th>Net</th></tr></thead>
            <tbody>
              <tr className={result.delta.net > 0 ? "good" : result.delta.net < 0 ? "bad" : "neutral"}>
                <td>{result.delta.give_value}</td>
                <td>{result.delta.get_value}</td>
                <td>{result.delta.net > 0 ? `+${result.delta.net}` : result.delta.net}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      <section className="trade-section">
        <h2>Trade history</h2>
        <TradeHistoryView />
      </section>
    </div>
  );
}
