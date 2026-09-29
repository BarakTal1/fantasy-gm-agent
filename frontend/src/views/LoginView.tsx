import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Zap, ArrowRight, Radar, Scale, TrendingUp } from "lucide-react";
import { useAuth } from "../state/auth";
import { ThemeToggle } from "../components/ThemeToggle";

const PERKS = [
  { icon: Radar, text: "Waiver-wire radar tuned to your open roster spots" },
  { icon: Scale, text: "Trade analysis that knows your league's scoring" },
  { icon: TrendingUp, text: "Buy-low and sell-high targets, refreshed nightly" },
];

export function LoginView({ theme, onToggle }: { theme: string; onToggle: () => void }) {
  const { user, ready, login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Already signed in — nothing to do here.
  if (ready && user) return <Navigate to="/app" replace />;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password);
      navigate("/app");
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <aside className="auth-aside">
        <Link to="/" className="brand auth-brand">
          <span className="mark"><Zap fill="currentColor" /></span>Lightning
        </Link>
        <div className="auth-aside-body">
          <h1 className="auth-aside-title">Your fantasy GM,<br />electrified.</h1>
          <ul className="auth-perks">
            {PERKS.map((p) => (
              <li key={p.text} className="auth-perk">
                <span className="auth-perk-icon"><p.icon size={16} /></span>
                {p.text}
              </li>
            ))}
          </ul>
        </div>
        <p className="auth-aside-foot">Runs on a real-NBA demo league — Yahoo sync coming soon.</p>
      </aside>

      <main className="auth-main">
        <div className="auth-topbar">
          <Link to="/" className="auth-back">← Back to home</Link>
          <ThemeToggle theme={theme} onToggle={onToggle} />
        </div>

        <div className="auth-card">
          <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
          <p className="modal-sub">
            {mode === "login"
              ? "Sign in to save your league format and settings."
              : "Sign up to save settings and, soon, connect your Yahoo league."}
          </p>
          <form onSubmit={submit} className="auth-form">
            <label>
              Email
              <input type="email" value={email} required autoComplete="email"
                     onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label>
              Password
              <input type="password" value={password} required minLength={6}
                     autoComplete={mode === "login" ? "current-password" : "new-password"}
                     onChange={(e) => setPassword(e.target.value)} />
            </label>
            {error && <p className="auth-error" role="alert">{error}</p>}
            <button type="submit" className="analyze-btn" disabled={busy}>
              {busy ? "…" : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>
          <button className="auth-switch"
                  onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}>
            {mode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}
          </button>
        </div>

        <Link to="/app" className="auth-skip">
          Skip — just explore the demo <ArrowRight size={15} />
        </Link>
      </main>
    </div>
  );
}
