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
        <div className="roster-name">
          {p.name}
          <span className="pos-tags">
            {p.positions.map((pos) => <span key={pos} className="pos-tag">{pos}</span>)}
          </span>
          <em>{p.nba_team} · {p.games} gm</em>
        </div>
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

  const best = data.best_player;
  const strongest = data.position_strengths[0];
  const valueLabel = data.format === "points" ? "pts" : "cat value";

  return (
    <div className="dashboard">
      <figure className="chart">
        <figcaption>Team analytics</figcaption>
        <div className="analytics-grid">
          {best && (
            <div className="stat-tile">
              <span className="stat-tile-label">Best player</span>
              <div className="stat-tile-main">
                <PlayerAvatar name={best.name} image_url={best.image_url} size={34} />
                <div>
                  <div className="stat-tile-value">{best.name}</div>
                  <div className="stat-tile-sub">
                    {best.positions.join("/")} · {best.value} {valueLabel}
                  </div>
                </div>
              </div>
            </div>
          )}
          {strongest && (
            <div className="stat-tile">
              <span className="stat-tile-label">Strongest position</span>
              <div className="stat-tile-value stat-tile-pos">{strongest.position}</div>
              <div className="stat-tile-sub">
                {strongest.count} players · {strongest.avg_value} avg {valueLabel}
              </div>
            </div>
          )}
        </div>
        <div className="pos-balance">
          <span className="pos-balance-label">Positional depth</span>
          <div className="pos-balance-row">
            {data.positional_balance.map((b) => (
              <div key={b.position} className={"pos-chip" + (b.thin ? " pos-chip-thin" : "")}>
                <span className="pos-chip-pos">{b.position}</span>
                <span className="pos-chip-count">{b.eligible}</span>
              </div>
            ))}
          </div>
          <p className="chart-hint">
            Players eligible at each slot (multi-position players count in each).
            {data.positional_balance.some((b) => b.thin) && " Gold = thin depth."}
          </p>
        </div>
      </figure>

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
