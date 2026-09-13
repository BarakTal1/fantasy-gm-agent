import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Moon, Sun, Link2, RefreshCw, Check } from "lucide-react";
import { useAuth } from "../state/auth";
import {
  getLeagueConfig, saveLeagueConfig, syncLeagueFromYahoo,
  type LeagueConfig,
} from "../lib/api";

type Format = "category" | "points";

export function SettingsView({ theme, onToggle }: { theme: string; onToggle: () => void }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [options, setOptions] = useState<LeagueConfig["options"] | null>(null);
  const [connected, setConnected] = useState(false);
  const [source, setSource] = useState<LeagueConfig["source"]>("demo");
  const [loadErr, setLoadErr] = useState<string | null>(null);

  // Editable fields
  const [name, setName] = useState("");
  const [format, setFormat] = useState<Format>("category");
  const [cats, setCats] = useState<string[]>([]);
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [slots, setSlots] = useState<Record<string, number>>({});

  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const hydrate = useCallback((c: LeagueConfig) => {
    setName(c.name);
    setFormat(c.format);
    setCats(c.categories);
    setWeights(c.point_weights);
    setSlots(c.roster_slots);
    setOptions(c.options);
    setConnected(c.yahoo_connected);
    setSource(c.source);
  }, []);

  useEffect(() => {
    if (!user) return;
    getLeagueConfig().then(hydrate).catch((e) => setLoadErr(String(e)));
  }, [user, hydrate]);

  const logoutAndLeave = async () => { await logout(); navigate("/"); };

  const toggleCat = (c: string) =>
    setCats((cur) => (cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c]));

  const setWeight = (stat: string, v: string) =>
    setWeights((cur) => ({ ...cur, [stat]: v === "" ? 0 : Number(v) }));

  const setSlot = (pos: string, v: string) =>
    setSlots((cur) => {
      const next = { ...cur };
      const n = v === "" ? 0 : Math.max(0, Math.floor(Number(v)));
      if (n > 0) next[pos] = n; else delete next[pos];
      return next;
    });

  const save = async () => {
    setError(null); setNotice(null); setSaving(true);
    try {
      const result = await saveLeagueConfig({
        name, format, categories: cats, point_weights: weights, roster_slots: slots,
      });
      hydrate(result);
      setNotice("League settings saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const sync = async () => {
    setError(null); setNotice(null); setSyncing(true);
    try {
      hydrate(await syncLeagueFromYahoo());
      setNotice("Synced from Yahoo.");
    } catch (e) {
      // Approval-gated: a 409 here is the expected "not connected yet" state.
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSyncing(false);
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
            <button className="signin-btn" onClick={logoutAndLeave}>Sign out</button>
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
        <h2>League settings</h2>
        {!user ? (
          <p className="settings-hint">Sign in to set up your league.</p>
        ) : loadErr ? (
          <p className="auth-error" role="alert">Failed to load settings: {loadErr}</p>
        ) : !options ? (
          <div className="skeleton skeleton-row" />
        ) : (
          <>
            {/* --- Set automatically from Yahoo --- */}
            <div className="settings-row cfg-sync-row">
              <span className="cfg-sync-label">
                <Link2 size={16} /> Set automatically from Yahoo
                {connected
                  ? <span className="cfg-src-tag cfg-src-live">Connected</span>
                  : <span className="soon-tag">Not connected</span>}
              </span>
              <button className="seg cfg-sync-btn" onClick={sync} disabled={syncing}>
                <RefreshCw size={15} className={syncing ? "spin" : ""} />
                {syncing ? "Syncing…" : "Sync from Yahoo"}
              </button>
            </div>
            <p className="settings-hint">
              {connected
                ? "Pulls your league name, scoring format, categories and roster from Yahoo."
                : "Yahoo Fantasy API access is pending approval. Set your league manually below — you can sync once it's connected."}
            </p>

            <hr className="cfg-divider" />

            {/* --- Manual editor --- */}
            <label className="cfg-field">
              <span className="cfg-field-label">League name</span>
              <input className="cfg-input" value={name} placeholder="My League"
                     onChange={(e) => setName(e.target.value)} />
            </label>

            <div className="cfg-field">
              <span className="cfg-field-label">Scoring format</span>
              <div className="segmented" role="radiogroup" aria-label="Scoring format">
                {(["category", "points"] as Format[]).map((f) => (
                  <button key={f} role="radio" aria-checked={format === f}
                          className={"seg" + (format === f ? " seg-active" : "")}
                          onClick={() => setFormat(f)}>
                    {f === "category" ? "Category" : "Points"}
                  </button>
                ))}
              </div>
            </div>

            {format === "category" ? (
              <div className="cfg-field">
                <span className="cfg-field-label">Scoring categories</span>
                <div className="cfg-chips">
                  {options.categories.map((c) => (
                    <button key={c} type="button"
                            aria-pressed={cats.includes(c)}
                            className={"cfg-chip" + (cats.includes(c) ? " cfg-chip-active" : "")}
                            onClick={() => toggleCat(c)}>
                      {c}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="cfg-field">
                <span className="cfg-field-label">Point weights</span>
                <div className="cfg-grid">
                  {options.point_stats.map((s) => (
                    <label key={s} className="cfg-num">
                      <span>{s}</span>
                      <input type="number" step="0.1" value={weights[s] ?? ""}
                             onChange={(e) => setWeight(s, e.target.value)} />
                    </label>
                  ))}
                </div>
              </div>
            )}

            <div className="cfg-field">
              <span className="cfg-field-label">Roster slots</span>
              <div className="cfg-grid">
                {options.positions.map((p) => (
                  <label key={p} className="cfg-num">
                    <span>{p}</span>
                    <input type="number" min="0" step="1" value={slots[p] ?? ""}
                           placeholder="0"
                           onChange={(e) => setSlot(p, e.target.value)} />
                  </label>
                ))}
              </div>
            </div>

            <div className="cfg-actions">
              <button className="analyze-btn" onClick={save} disabled={saving}>
                {saving ? "Saving…" : "Save league settings"}
              </button>
              {source === "manual" && !notice && (
                <span className="cfg-src-tag">Manual config active</span>
              )}
              {notice && <span className="cfg-notice"><Check size={14} /> {notice}</span>}
            </div>
            {error && <p className="auth-error" role="alert">{error}</p>}
          </>
        )}
      </section>
    </div>
  );
}
