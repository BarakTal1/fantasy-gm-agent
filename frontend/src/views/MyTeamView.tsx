import { useEffect, useState } from "react";
import { getMyTeamAnalytics } from "../lib/api";
import { RadarChart } from "../components/charts/RadarChart";
import { WeekdayBars } from "../components/charts/WeekdayBars";
import { ErrorBanner } from "../components/ErrorBanner";

type Payload = Awaited<ReturnType<typeof getMyTeamAnalytics>>;

export function MyTeamView() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null); setData(null);
    getMyTeamAnalytics().then(setData).catch((e) => setError(String(e)));
  };
  useEffect(load, []);

  if (error) return <ErrorBanner message={`Failed to load My Team: ${error}`} onRetry={load} />;
  if (!data) {
    return (
      <div className="dashboard" aria-busy="true" aria-live="polite">
        <span className="sr-table">Loading…</span>
        <div className="skeleton skeleton-block" />
        <div className="skeleton skeleton-block" />
      </div>
    );
  }

  const cats = data.category_profile ? Object.keys(data.category_profile) : [];
  const you = cats.map((c) => data.category_profile![c].you);
  const league = cats.map((c) => data.category_profile![c].league_avg);

  return (
    <div className="dashboard">
      {cats.length > 0 && <RadarChart cats={cats} you={you} league={league} />}
      <WeekdayBars days={data.weekdays} />
    </div>
  );
}
