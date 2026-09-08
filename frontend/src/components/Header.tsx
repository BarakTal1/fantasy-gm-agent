import { ThemeToggle } from "./ThemeToggle";

export function Header({ theme, onToggle }: { theme: string; onToggle: () => void }) {
  return (
    <header className="header">
      <div className="brand"><span className="mark" />Fantasy GM</div>
      <span className="league">Dubs Dynasty · 9-cat</span>
      <ThemeToggle theme={theme} onToggle={onToggle} />
    </header>
  );
}
