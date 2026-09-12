import { useEffect, useState } from "react";
import { getWaiversAnalytics, type RecommendedPickup } from "../lib/api";
import { BarList } from "../components/charts/BarList";
import { GamesHeatmap } from "../components/charts/GamesHeatmap";
import { ErrorBanner } from "../components/ErrorBanner";

type Payload = Awaited<ReturnType<typeof getWaiversAnalytics>>;

function RecommendedPickups({ items }: { items: RecommendedPickup[] }) {
  return (
    <figure className="chart">
      <figcaption>Recommended pickups</figcaption>
      <ul className="pickups">
        {items.map((r) => (
          <li key={r.player_id} className="pickup-row">
            <span className="pickup-add">Add {r.name} <em>{r.nba_team} · {r.games} gm</em></span>
            {r.drop && <span className="pickup-drop">drop {r.drop.name}</span>}
          </li>
        ))}
      </ul>
      <table className="sr-table">
        <caption>Recommended pickups</caption>
        <thead><tr><th>Add</th><th>Team</th><th>Games</th><th>Drop</th></tr></thead>
        <tbody>{items.map((r) => (
          <tr key={r.player_id}>
            <td>{r.name}</td><td>{r.nba_team}</td><td>{r.games}</td>
            <td>{r.drop ? r.drop.name : "—"}</td>
          </tr>
        ))}</tbody>
      </table>
    </figure>
  );
}

export function WaiversView() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null); setData(null);
    getWaiversAnalytics().then(setData).catch((e) => setError(String(e)));
  };
  useEffect(load, []);

  if (error) return <ErrorBanner message={`Failed to load Waivers: ${error}`} onRetry={load} />;
  if (!data) {
    return (
      <div className="dashboard" aria-busy="true" aria-live="polite">
        <span className="sr-table">Loading…</span>
        <div className="skeleton skeleton-block" />
        <div className="skeleton skeleton-block" />
      </div>
    );
  }

  const hasContent = data.recommended_pickups.length > 0 ||
    (data.format === "points" ? (data.points_value_board?.length ?? 0) > 0
      : (data.streaming_board?.length ?? 0) > 0);
  if (!hasContent) {
    return <div className="empty">No recommendations right now — check back after games tonight.</div>;
  }

  const board = data.format === "points"
    ? (data.points_value_board ?? []).map((r) => ({
        label: r.name, value: r.projected_points, sub: `${r.nba_team} · ${r.games} gm` }))
    : (data.streaming_board ?? []).map((r) => ({
        label: r.name, value: r.score, sub: `${r.nba_team} · ${r.games} gm` }));

  return (
    <div className="dashboard">
      <BarList title={data.format === "points" ? "Points value board" : "Streaming board"}
               items={board} />
      <RecommendedPickups items={data.recommended_pickups} />
      <GamesHeatmap games={data.schedule} />
    </div>
  );
}
