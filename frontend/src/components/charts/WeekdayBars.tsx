import type { WeekdayCoverage } from "../../lib/api";

export function WeekdayBars({ days }: { days: WeekdayCoverage[] }) {
  const max = Math.max(1, ...days.map((d) => d.count));
  const weakDays = days.filter((d) => d.weak).map((d) => d.day);
  const heavyDays = days.filter((d) => d.heavy).map((d) => d.day);
  const hints = [];
  if (weakDays.length) hints.push(`Thin on ${weakDays.join(" & ")} — grab waiver players who play those days.`);
  if (heavyDays.length) hints.push(`Overloaded on ${heavyDays.join(" & ")} — 10+ players, wasted production; spread your games out.`);
  if (!hints.length) hints.push("Balanced coverage every day this week.");

  return (
    <figure className="chart">
      <figcaption>Games this week by day</figcaption>
      <div className="weekbars">
        {days.map((d) => (
          <div className={"weekcol" + (d.weak ? " weak" : "") + (d.heavy ? " heavy" : "")} key={d.day}>
            <span className="weekcount">{d.count}</span>
            <span className="weektrack">
              <span className="weekfill" style={{ height: `${(d.count / max) * 100}%` }} />
            </span>
            <span className="weekday">{d.day}</span>
            {d.weak && <span className="weektag">stream</span>}
            {d.heavy && <span className="weektag heavy">waste</span>}
          </div>
        ))}
      </div>
      {hints.map((h) => <p className="chart-hint" key={h}>{h}</p>)}
      <table className="sr-table">
        <caption>Players with a game each day this week</caption>
        <thead><tr><th>Day</th><th>Players</th><th>Thin</th><th>Overloaded</th></tr></thead>
        <tbody>{days.map((d) => (
          <tr key={d.day}><td>{d.day}</td><td>{d.count}</td>
            <td>{d.weak ? "yes" : "no"}</td><td>{d.heavy ? "yes" : "no"}</td></tr>
        ))}</tbody>
      </table>
    </figure>
  );
}
