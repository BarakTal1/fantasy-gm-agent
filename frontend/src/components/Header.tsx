import { useEffect, useState } from "react";
import { Zap } from "lucide-react";
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
      <div className="brand"><span className="mark"><Zap fill="currentColor" /></span>Lightning</div>
      {league && <span className="league">{league}</span>}
      <ThemeToggle theme={theme} onToggle={onToggle} />
    </header>
  );
}
