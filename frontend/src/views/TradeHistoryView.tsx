import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import { getTradeHistory } from "../lib/api";
import type { HistoricTrade } from "../lib/api";
import { TradePlayerRow } from "../components/TradePlayerRow";
import { ErrorBanner } from "../components/ErrorBanner";

export function TradeHistoryView() {
  const [trades, setTrades] = useState<HistoricTrade[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    setTrades(null);
    getTradeHistory().then((d) => setTrades(d.trades)).catch((e) => setError(String(e)));
  };
  useEffect(load, []);

  if (error) return <ErrorBanner message={`Failed to load trade history: ${error}`} onRetry={load} />;
  if (!trades) {
    return (
      <div className="history" aria-busy="true" aria-live="polite">
        <span className="sr-table">Loading trade history…</span>
        <div className="skeleton skeleton-block" />
        <div className="skeleton skeleton-block" />
      </div>
    );
  }
  if (trades.length === 0) {
    return <div className="empty">No trades yet this season.</div>;
  }

  return (
    <div className="history">
      <p className="settings-hint">
        Demo trades — click a player to see their before/after. Real history connects with Yahoo.
      </p>
      {trades.map((t, i) => (
        <section className="trade-card" key={i}>
          <header className="trade-card-head">
            <span className="trade-date">{t.date}</span>
            <span className="trade-with">with {t.with_team}</span>
          </header>
          <div className="trade-sides">
            <div className="trade-side">
              <h3>You gave</h3>
              {t.gave.map((p) => <TradePlayerRow key={p.player_id} player={p} side="gave" />)}
            </div>
            <ArrowRight className="trade-arrow" size={20} aria-hidden="true" />
            <div className="trade-side">
              <h3>You got</h3>
              {t.got.map((p) => <TradePlayerRow key={p.player_id} player={p} side="got" />)}
            </div>
          </div>
        </section>
      ))}
    </div>
  );
}
