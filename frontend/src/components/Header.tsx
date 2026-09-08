import { useEffect, useState } from "react";
import { getLeagueInfo } from "../lib/api";
import { ThemeToggle } from "./ThemeToggle";

export function Header({ theme, onToggle }: { theme: string; onToggle: () => void }) {
  const [league, setLeague] = useState("");
  useEffect(() => {
    getLeagueInfo()
      .then((i) => setLeague(i.name ? `${i.name} · ${i.format_label}` : i.format_label))
      .catch(() => setLeague(""));
  }, []);
  return (
    <header className="header">
      <div className="brand"><span className="mark" />Fantasy GM</div>
      {league && <span className="league">{league}</span>}
      <ThemeToggle theme={theme} onToggle={onToggle} />
    </header>
  );
}
