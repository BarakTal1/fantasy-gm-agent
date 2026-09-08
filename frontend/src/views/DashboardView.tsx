import { useEffect, useState } from "react";
import { getDashboard } from "../lib/api";
import { RadarChart } from "../components/charts/RadarChart";
import { BarList } from "../components/charts/BarList";
import { DivergingList } from "../components/charts/DivergingList";
import { GamesHeatmap } from "../components/charts/GamesHeatmap";
import { ErrorBanner } from "../components/ErrorBanner";

interface RecommendedPickup {
  player_id: string; name: string; nba_team: string; games: number; score: number;
  drop: { player_id: string; name: string; value: number } | null;
}

interface CategoryDashboardPayload {
  format: "category";
  schedule: Record<string, number>;
  recommended_pickups: RecommendedPickup[];
  buy_low_sell_high: { player_id: string; name: string; delta_pct: number;
                       signal: "buy_low" | "sell_high" }[];
  category_profile: Record<string, { you: number; league_avg: number }>;
  streaming_board: { player_id: string; name: string; nba_team: string; games: number;
                     projected: Record<string, number>; score: number }[];
}

interface PointsDashboardPayload {
  format: "points";
  schedule: Record<string, number>;
  recommended_pickups: RecommendedPickup[];
  buy_low_sell_high: never[];
  points_value_board: { player_id: string; name: string; nba_team: string; games: number;
                        projected_points: number }[];
}

type DashboardPayload = CategoryDashboardPayload | PointsDashboardPayload;

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

export function DashboardView() {
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    setData(null);
    getDashboard()
      .then((d) => setData(d))
      .catch((e) => setError(String(e)));
  };

  useEffect(load, []);

  if (error) return <ErrorBanner message={`Failed to load dashboard: ${error}`} onRetry={load} />;
  if (!data) return <div className="empty">Loading dashboard…</div>;

  const hasRecommendations = data.recommended_pickups.length > 0;
  const hasAnyContent = hasRecommendations ||
    (data.format === "category" ? data.streaming_board.length > 0 || data.buy_low_sell_high.length > 0
      : data.points_value_board.length > 0);

  if (!hasAnyContent) {
    return <div className="empty">No recommendations right now — check back after games tonight.</div>;
  }

  if (data.format === "points") {
    const pointsItems = data.points_value_board.map((r) => ({
      label: r.name, value: r.projected_points, sub: `${r.nba_team} · ${r.games} gm`,
    }));
    return (
      <div className="dashboard">
        <BarList title="Points value board" items={pointsItems} />
        <RecommendedPickups items={data.recommended_pickups} />
        <GamesHeatmap games={data.schedule} />
      </div>
    );
  }

  const cats = Object.keys(data.category_profile);
  const you = cats.map((c) => data.category_profile[c].you);
  const league = cats.map((c) => data.category_profile[c].league_avg);

  const streamingItems = data.streaming_board.map((r) => ({
    label: r.name, value: r.score, sub: `${r.nba_team} · ${r.games} gm`,
  }));

  const divergingItems = data.buy_low_sell_high.map((r) => ({
    label: r.name, value: r.delta_pct, signal: r.signal,
  }));

  return (
    <div className="dashboard">
      <RadarChart cats={cats} you={you} league={league} />
      <RecommendedPickups items={data.recommended_pickups} />
      <BarList title="Streaming board" items={streamingItems} />
      <DivergingList items={divergingItems} />
      <GamesHeatmap games={data.schedule} />
    </div>
  );
}
