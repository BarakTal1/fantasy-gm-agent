export function RadarChart({ cats, you, league }: {
  cats: string[]; you: number[]; league: number[];
}) {
  const N = cats.length, R = 90, cx = 110, cy = 110;
  const maxes = cats.map((_, i) => Math.max(1, you[i], league[i]));
  const pt = (i: number, v: number) => {
    const a = (Math.PI * 2 * i) / N - Math.PI / 2;
    const r = (v / maxes[i]) * R;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  };
  const poly = (vals: number[]) =>
    vals.map((v, i) => pt(i, v).join(",")).join(" ");
  return (
    <figure className="chart">
      <figcaption>Category profile — you vs league average</figcaption>
      <svg viewBox="0 0 220 240" width="100%" role="img"
           aria-label="Category strengths versus the league average">
        {[0.33, 0.66, 1].map((f) => (
          <circle key={f} cx={cx} cy={cy} r={R * f} className="radar-grid" />
        ))}
        {cats.map((c, i) => {
          const [x, y] = pt(i, maxes[i]);
          return <text key={c} x={x} y={y} className="radar-axis"
                       textAnchor="middle">{c}</text>;
        })}
        <polygon points={poly(league)} className="radar-league" />
        <polygon points={poly(you)} className="radar-you" />
      </svg>
      <div className="legend">
        <span><i className="sw you" /> You</span>
        <span><i className="sw league" /> League avg</span>
      </div>
      <table className="sr-table">
        <caption>Category profile — you vs league average</caption>
        <thead><tr><th>Category</th><th>You</th><th>League avg</th></tr></thead>
        <tbody>{cats.map((c, i) =>
          <tr key={c}><td>{c}</td><td>{you[i]}</td><td>{league[i]}</td></tr>)}</tbody>
      </table>
    </figure>
  );
}
