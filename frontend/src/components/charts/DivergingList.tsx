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
    </figure>
  );
}
