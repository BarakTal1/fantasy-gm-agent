import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Zap, Settings, LogOut, User } from "lucide-react";
import { getLeagueInfo } from "../lib/api";
import { useAuth } from "../state/auth";
import { AuthModal } from "./AuthModal";
import { ThemeToggle } from "./ThemeToggle";

export function Header({ theme, onToggle }: { theme: string; onToggle: () => void }) {
  const [league, setLeague] = useState("");
  const [showAuth, setShowAuth] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const { user, ready, logout } = useAuth();

  useEffect(() => {
    getLeagueInfo()
      .then((i) => setLeague(i.name ? `${i.name} · ${i.format_label}` : i.format_label))
      .catch(() => setLeague(""));
  }, [user]); // re-read after login/logout in case the format changed

  return (
    <header className="header">
      <div className="brand"><span className="mark"><Zap fill="currentColor" /></span>Lightning</div>
      {league && <span className="league">{league}</span>}
      <div className="header-right">
        <ThemeToggle theme={theme} onToggle={onToggle} />
        {ready && !user && (
          <button className="signin-btn" onClick={() => setShowAuth(true)}>Sign in</button>
        )}
        {ready && user && (
          <div className="account" onBlur={() => setMenuOpen(false)} tabIndex={-1}>
            <button className="account-btn" aria-haspopup="menu" aria-expanded={menuOpen}
                    onClick={() => setMenuOpen((o) => !o)}>
              <User size={16} /> <span className="account-email">{user.email}</span>
            </button>
            {menuOpen && (
              <div className="account-menu" role="menu">
                <Link to="/settings" role="menuitem" className="account-item"
                      onClick={() => setMenuOpen(false)}>
                  <Settings size={15} /> Settings
                </Link>
                <button role="menuitem" className="account-item"
                        onClick={() => { setMenuOpen(false); logout(); }}>
                  <LogOut size={15} /> Sign out
                </button>
              </div>
            )}
          </div>
        )}
      </div>
      {showAuth && <AuthModal onClose={() => setShowAuth(false)} />}
    </header>
  );
}
