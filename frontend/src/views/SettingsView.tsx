import { useState } from "react";
import { Link } from "react-router-dom";
import { Moon, Sun, Link2 } from "lucide-react";
import { useAuth } from "../state/auth";
import { updateSettings } from "../lib/api";

export function SettingsView({ theme, onToggle }: { theme: string; onToggle: () => void }) {
  const { user, setUser, logout } = useAuth();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chooseFormat = async (fmt: string) => {
    if (!user || fmt === user.league_format) return;
    setError(null);
    setSaving(true);
    try {
      await updateSettings(fmt);
      setUser({ ...user, league_format: fmt });
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="settings">
      <h1>Settings</h1>

      <section className="settings-card">
        <h2>Account</h2>
        {user ? (
          <div className="settings-row">
            <span>{user.email}</span>
            <button className="signin-btn" onClick={logout}>Sign out</button>
          </div>
        ) : (
          <p className="settings-hint">
            <Link to="/login" className="settings-signin-link">Sign in</Link> to save your settings.
          </p>
        )}
      </section>

      <section className="settings-card">
        <h2>Appearance</h2>
        <div className="settings-row">
          <span>Theme</span>
          <button className="seg" onClick={onToggle}>
            {theme === "dark" ? <><Moon size={15} /> Dark</> : <><Sun size={15} /> Light</>}
          </button>
        </div>
      </section>

      <section className="settings-card">
        <h2>League format</h2>
        {user ? (
          <>
            <div className="segmented" role="radiogroup" aria-label="League format">
              {["category", "points"].map((f) => (
                <button key={f} role="radio" aria-checked={user.league_format === f}
                        disabled={saving}
                        className={"seg" + (user.league_format === f ? " seg-active" : "")}
                        onClick={() => chooseFormat(f)}>
                  {f === "category" ? "Category (9-cat)" : "Points"}
                </button>
              ))}
            </div>
            <p className="settings-hint">Changes what the dashboard and trade analyzer optimize for.</p>
            {error && <p className="auth-error" role="alert">{error}</p>}
          </>
        ) : (
          <p className="settings-hint">Sign in to choose your league's scoring format.</p>
        )}
      </section>

      <section className="settings-card settings-soon">
        <h2><Link2 size={16} /> Connect Yahoo</h2>
        <div className="settings-row">
          <span>Sync your real Yahoo Fantasy league — roster, transactions, live stats.</span>
          <span className="soon-tag">Coming soon</span>
        </div>
        <p className="settings-hint">
          Pending Yahoo Fantasy API approval. Until then the app runs on a real-NBA demo league.
        </p>
      </section>
    </div>
  );
}
