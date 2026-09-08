export function GamesHeatmap({ games }: { games: Record<string, number> }) {
  const max = Math.max(1, ...Object.values(games));
  const entries = Object.entries(games).sort((a, b) => b[1] - a[1]);
  return (
    <figure className="chart">
      <figcaption>Games this week</figcaption>
      <div className="heat">
        {entries.map(([team, g]) => (
          <div className="cell" key={team}
               style={{ background: `color-mix(in srgb, var(--primary) ${(g / max) * 100}%, transparent)` }}>
            <b>{team}</b><span>{g}</span>
          </div>
        ))}
      </div>
      <table className="sr-table">
        <caption>Games this week</caption>
        <thead><tr><th>Team</th><th>Games</th></tr></thead>
        <tbody>{entries.map(([team, g]) =>
          <tr key={team}><td>{team}</td><td>{g}</td></tr>)}</tbody>
      </table>
    </figure>
  );
}
