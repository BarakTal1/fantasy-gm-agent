import type { WeekdayCoverage } from "../../lib/api";

export function WeekdayBars({ days }: { days: WeekdayCoverage[] }) {
  const max = Math.max(1, ...days.map((d) => d.count));
  const weakDays = days.filter((d) => d.weak).map((d) => d.day);
  const hint = weakDays.length
    ? `Thin on ${weakDays.join(" & ")} — grab waiver players who play those days.`
    : "Solid coverage every day this week.";

  return (
    <figure className="chart">
      <figcaption>Games this week by day</figcaption>
      <div className="weekbars">
        {days.map((d) => (
          <div className={"weekcol" + (d.weak ? " weak" : "")} key={d.day}>
            <span className="weekcount">{d.count}</span>
            <span className="weektrack">
              <span className="weekfill" style={{ height: `${(d.count / max) * 100}%` }} />
            </span>
            <span className="weekday">{d.day}</span>
            {d.weak && <span className="weektag">stream</span>}
          </div>
        ))}
      </div>
      <p className="chart-hint">{hint}</p>
      <table className="sr-table">
        <caption>Players with a game each day this week</caption>
        <thead><tr><th>Day</th><th>Players playing</th><th>Thin day</th></tr></thead>
        <tbody>{days.map((d) => (
          <tr key={d.day}><td>{d.day}</td><td>{d.count}</td><td>{d.weak ? "yes" : "no"}</td></tr>
        ))}</tbody>
      </table>
    </figure>
  );
}
