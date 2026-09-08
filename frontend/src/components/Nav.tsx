import { NavLink } from "react-router-dom";

const TABS = [
  { to: "/", label: "Chat" },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/trade", label: "Trade" },
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
