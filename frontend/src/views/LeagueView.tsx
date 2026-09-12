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

  return (
    <div className="dashboard">
      <figure className="chart">
        <figcaption>League teams</figcaption>
        <table className="delta-table">
          <thead><tr><th>Team</th><th>Players</th></tr></thead>
          <tbody>
            {data.teams.map((t) => (
              <tr key={t.team_key} className={t.team_key === data.my_team_key ? "good" : ""}>
                <td>{t.name}{t.team_key === data.my_team_key && <em> (you)</em>}</td>
                <td>{t.players.length}</td>
              </tr>
            ))}
          </tbody>
        </table>
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
