import { useState } from "react";
import { analyzeTrade } from "../lib/api";
import { ErrorBanner } from "./ErrorBanner";

interface Result {
  verdict: string;
  recommendation: "ACCEPT" | "DECLINE" | "COUNTER";
  delta: Record<string, number> | { give_value: number; get_value: number; net: number };
}

/** Strip the trailing ACCEPT/DECLINE/COUNTER keyword the backend appends. */
function narrativeOnly(verdict: string, recommendation: string): string {
  return verdict.replace(new RegExp(`\\s*${recommendation}\\.?\\s*$`), "").trim();
}

/** Shared "Analyze" action used by received offers and suggested trades.
 * Pre-fills give/get and runs the existing Claude verdict endpoint on demand. */
export function AnalyzeTrade({ give, get }: { give: string[]; get: string[] }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);

  const run = async () => {
    setLoading(true); setError(null);
    try {
      setResult(await analyzeTrade(give, get) as Result);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="analyze-trade">
      <button type="button" className="analyze-btn" disabled={loading} onClick={run}>
        {loading ? "Analyzing…" : "Analyze"}
      </button>
      {error && <ErrorBanner message={`Failed to analyze trade: ${error}`} onRetry={run} />}
      {result && (
        <div className={`verdict-card rec-${result.recommendation.toLowerCase()}`}>
          <span className="badge">{result.recommendation}</span>
          <p>{narrativeOnly(result.verdict, result.recommendation)}</p>
        </div>
      )}
    </div>
  );
}
