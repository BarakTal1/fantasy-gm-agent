import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Zap, Settings, LogOut, User } from "lucide-react";
import { getLeagueInfo } from "../lib/api";
import { useAuth } from "../state/auth";
import { ThemeToggle } from "./ThemeToggle";

export function Header({ theme, onToggle }: { theme: string; onToggle: () => void }) {
  const [league, setLeague] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const accountRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { user, ready, logout } = useAuth();

  useEffect(() => {
    getLeagueInfo()
      .then((i) => setLeague(i.name ? `${i.name} · ${i.format_label}` : i.format_label))
      .catch(() => setLeague(""));
  }, [user]); // re-read after login/logout in case the format changed

  // Close the account menu on an outside click or Escape. (A previous onBlur
  // handler closed the menu on focusout *before* the click on a menu item could
  // register, so Sign out / Settings never fired — this is the reliable pattern.)
  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: MouseEvent) => {
      if (accountRef.current && !accountRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setMenuOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const handleLogout = async () => {
    setMenuOpen(false);
    await logout();
    navigate("/");   // leave the authed app shell after signing out
  };

  return (
    <header className="header">
      <Link to="/app" className="brand">
        <span className="mark"><Zap fill="currentColor" /></span>Lightning
      </Link>
      {league && <span className="league">{league}</span>}
      <div className="header-right">
        <ThemeToggle theme={theme} onToggle={onToggle} />
        {ready && !user && (
          <Link className="signin-btn" to="/login">Sign in</Link>
        )}
        {ready && user && (
          <div className="account" ref={accountRef}>
            <button className="account-btn" aria-haspopup="menu" aria-expanded={menuOpen}
                    onClick={() => setMenuOpen((o) => !o)}>
              <User size={16} /> <span className="account-email">{user.email}</span>
            </button>
            {menuOpen && (
              <div className="account-menu" role="menu">
                <Link to="/app/settings" role="menuitem" className="account-item"
                      onClick={() => setMenuOpen(false)}>
                  <Settings size={15} /> Settings
                </Link>
                <button role="menuitem" className="account-item" onClick={handleLogout}>
                  <LogOut size={15} /> Sign out
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
