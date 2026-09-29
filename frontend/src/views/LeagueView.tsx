import { useEffect, useState } from "react";
import { getLeagueAnalytics } from "../lib/api";
import { DivergingList } from "../components/charts/DivergingList";
import { ErrorBanner } from "../components/ErrorBanner";

type Payload = Awaited<ReturnType<typeof getLeagueAnalytics>>;

export function LeagueView() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null); setData(null);
    getLeagueAnalytics().then(setData).catch((e) => setError(String(e)));
  };
  useEffect(load, []);

  if (error) return <ErrorBanner message={`Failed to load League: ${error}`} onRetry={load} />;
  if (!data) {
    return (
      <div className="dashboard" aria-busy="true" aria-live="polite">
        <span className="sr-table">Loading…</span>
        <div className="skeleton skeleton-block" />
      </div>
    );
  }

  // Map signed strength onto the diverging list: sell_high positive, buy_low negative.
  const divergingItems = data.buy_low_sell_high.map((r) => ({
    label: r.name,
    value: Math.round((r.signal === "sell_high" ? r.strength : -r.strength) * 100),
    signal: r.signal,
  }));

  // Column order comes from the first team's stat keys (server orders by the
  // league's categories / core box score).
  const statCols = data.team_stats[0] ? Object.keys(data.team_stats[0].stats) : [];
  const fmtStat = (c: string, v: number) => (c.endsWith("%") ? v.toFixed(3) : v);

  return (
    <div className="dashboard">
      <figure className="chart">
        <figcaption>League teams — season per-game totals</figcaption>
        <table className="delta-table">
          <thead>
            <tr>
              <th>Team</th><th>GP</th>
              {statCols.map((c) => <th key={c}>{c}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.team_stats.map((t) => (
              <tr key={t.team_key} className={t.team_key === data.my_team_key ? "good" : ""}>
                <td>{t.name}{t.team_key === data.my_team_key && <em> (you)</em>}</td>
                <td>{t.games_week}</td>
                {statCols.map((c) => <td key={c}>{fmtStat(c, t.stats[c])}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="chart-hint">
          Counting stats sum across the roster; FG%/FT% average. GP = total games
          your players' NBA teams play this week.
        </p>
      </figure>

      {divergingItems.length > 0 && (
        <>
          <DivergingList items={divergingItems} />
          <ul className="buy-sell-drivers">
            {data.buy_low_sell_high.map((r) => (
              <li key={r.player_id}>
                <strong>{r.name}</strong> — {r.signal === "buy_low" ? "buy low" : "sell high"}
                {r.drivers.length > 0 && <em> ({r.drivers.join(", ")})</em>}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
