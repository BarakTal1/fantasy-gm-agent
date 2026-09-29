import { NavLink } from "react-router-dom";

const TABS = [
  { to: "/app", label: "Chat", end: true },
  { to: "/app/my-team", label: "My Team", end: false },
  { to: "/app/waivers", label: "Waivers", end: false },
  { to: "/app/trade", label: "Trade", end: false },
  { to: "/app/league", label: "League", end: false },
];

export function Nav() {
  return (
    <nav className="nav">
      {TABS.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.end}
          className={({ isActive }) => "tab" + (isActive ? " active" : "")}
        >
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}
