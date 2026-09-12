import { useEffect, useState } from "react";
import { getMyTeamAnalytics, type RosterOutlookRow } from "../lib/api";
import { RadarChart } from "../components/charts/RadarChart";
import { PlayerAvatar } from "../components/PlayerAvatar";
import { ErrorBanner } from "../components/ErrorBanner";

type Payload = Awaited<ReturnType<typeof getMyTeamAnalytics>>;

const FORM_LABEL = { buy_low: "buy low", sell_high: "sell high", neutral: "neutral" } as const;

function RosterCard({ p }: { p: RosterOutlookRow }) {
  const proj = p.projected
    ? Object.entries(p.projected).filter(([c]) => c !== "TO")
        .map(([c, v]) => `${c} ${v}`).join(" · ")
    : `${p.projected_points ?? 0} pts`;
  return (
    <li className="roster-card">
      <PlayerAvatar name={p.name} image_url={p.image_url} />
      <div className="roster-main">
        <div className="roster-name">{p.name} <em>{p.nba_team} · {p.games} gm</em></div>
        <div className="roster-proj">{proj}</div>
      </div>
      <span className={`form-tag form-${p.form}`}>{FORM_LABEL[p.form]}</span>
    </li>
  );
}

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
      </div>
    );
  }

  const cats = data.category_profile ? Object.keys(data.category_profile) : [];
  const you = cats.map((c) => data.category_profile![c].you);
  const league = cats.map((c) => data.category_profile![c].league_avg);

  return (
    <div className="dashboard">
      <figure className="chart">
        <figcaption>Your roster — this week</figcaption>
        <ul className="roster-list">
          {data.roster.map((p) => <RosterCard key={p.player_id} p={p} />)}
        </ul>
      </figure>
      {cats.length > 0 && <RadarChart cats={cats} you={you} league={league} />}
    </div>
  );
}
