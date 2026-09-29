export function DivergingList({ items }: {
  items: { label: string; value: number; signal: "buy_low" | "sell_high" }[];
}) {
  return (
    <figure className="chart">
      <figcaption>Buy-low / Sell-high (14-day vs season)</figcaption>
      <ul className="diverging">
        {items.map((i) => (
          <li key={i.label} className={i.signal}>
            <span>{i.label}</span>
            <span className="tag">{i.signal === "buy_low" ? "buy low" : "sell high"} · {i.value}%</span>
          </li>
        ))}
      </ul>
      <table className="sr-table">
        <caption>Buy-low / sell-high signals</caption>
        <thead><tr><th>Player</th><th>Signal</th><th>14-day vs season</th></tr></thead>
        <tbody>{items.map((i) => (
          <tr key={i.label}>
            <td>{i.label}</td>
            <td>{i.signal === "buy_low" ? "Buy-low" : "Sell-high"}</td>
            <td>{i.value}%</td>
          </tr>
        ))}</tbody>
      </table>
    </figure>
  );
}
