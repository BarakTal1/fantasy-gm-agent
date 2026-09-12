import { NavLink } from "react-router-dom";

const TABS = [
  { to: "/", label: "Chat" },
  { to: "/my-team", label: "My Team" },
  { to: "/waivers", label: "Waivers" },
  { to: "/trade", label: "Trade" },
  { to: "/league", label: "League" },
];

export function Nav() {
  return (
    <nav className="nav">
      {TABS.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end
          className={({ isActive }) => "tab" + (isActive ? " active" : "")}
        >
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}
