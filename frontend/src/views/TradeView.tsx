import { useState } from "react";
import { analyzeTrade } from "../lib/api";

interface TradeResult {
  delta: Record<string, number>;
  summary: { improved: string[]; worsened: string[] };
  verdict: string;
  recommendation: "ACCEPT" | "DECLINE" | "COUNTER";
}

function parseIds(raw: string): string[] {
  return raw.split(",").map((s) => s.trim()).filter(Boolean);
}

/** Strip the trailing ACCEPT/DECLINE/COUNTER keyword the backend appends to the verdict,
 * since the recommendation badge already surfaces it — avoids showing it twice. */
function narrativeOnly(verdict: string, recommendation: string): string {
  return verdict.replace(new RegExp(`\\s*${recommendation}\\.?\\s*$`), "").trim();
}

export function TradeView() {
  const [give, setGive] = useState("");
  const [get, setGet] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TradeResult | null>(null);

  const analyze = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await analyzeTrade(parseIds(give), parseIds(get));
      setResult(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="trade">
      <form
        className="trade-form"
        onSubmit={(e) => { e.preventDefault(); analyze(); }}
      >
        <label htmlFor="give-input">Players to give (comma-separated ids)</label>
        <input id="give-input" value={give} onChange={(e) => setGive(e.target.value)} />

        <label htmlFor="get-input">Players to get (comma-separated ids)</label>
        <input id="get-input" value={get} onChange={(e) => setGet(e.target.value)} />

        <button type="submit" disabled={loading}>
          {loading ? "Analyzing…" : "Analyze"}
        </button>
      </form>

      {error && <div className="banner" role="alert">Failed to analyze trade: {error}</div>}

      {result && (
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
    </div>
  );
}
