import { useEffect, useState } from "react";
import { getDashboard } from "../lib/api";
import { RadarChart } from "../components/charts/RadarChart";
import { BarList } from "../components/charts/BarList";
import { DivergingList } from "../components/charts/DivergingList";
import { GamesHeatmap } from "../components/charts/GamesHeatmap";

interface DashboardPayload {
  category_profile: Record<string, { you: number; league_avg: number }>;
  streaming_board: {
    player_id: string; name: string; nba_team: string; games: number;
    projected: Record<string, number>; score: number;
  }[];
  buy_low_sell_high: {
    player_id: string; name: string; delta_pct: number;
    signal: "buy_low" | "sell_high";
  }[];
  schedule: Record<string, number>;
}

export function DashboardView() {
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    getDashboard()
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(String(e)); });
    return () => { cancelled = true; };
  }, []);

  if (error) return <div className="banner" role="alert">Failed to load dashboard: {error}</div>;
  if (!data) return <div className="empty">Loading dashboard…</div>;

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
      <BarList title="Streaming board" items={streamingItems} />
      <DivergingList items={divergingItems} />
      <GamesHeatmap games={data.schedule} />
    </div>
  );
}
