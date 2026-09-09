import { useState } from "react";
import { X } from "lucide-react";
import { useAuth } from "../state/auth";

export function AuthModal({ onClose }: { onClose: () => void }) {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password);
      onClose();
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label="Sign in"
           onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Close">
          <X size={18} />
        </button>
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
    </div>
  );
}
