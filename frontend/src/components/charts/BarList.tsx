export function BarList({ title, items }: {
  title: string; items: { label: string; value: number; sub?: string }[];
}) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <figure className="chart">
      <figcaption>{title}</figcaption>
      <div className="barlist">
        {items.map((i) => (
          <div className="barrow" key={i.label}>
            <span className="blabel">{i.label}{i.sub && <em> {i.sub}</em>}</span>
            <span className="btrack">
              <span className="bfill" style={{ width: `${(i.value / max) * 100}%` }} />
            </span>
            <span className="bval">{i.value}</span>
          </div>
        ))}
      </div>
      <table className="sr-table">
        <caption>{title}</caption>
        <thead><tr><th>Player</th><th>Value</th></tr></thead>
        <tbody>{items.map((i) =>
          <tr key={i.label}>
            <td>{i.label}{i.sub ? ` — ${i.sub}` : ""}</td>
            <td>{i.value}</td>
          </tr>)}</tbody>
      </table>
    </figure>
  );
}
