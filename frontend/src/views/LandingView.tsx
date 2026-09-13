import { Link, Navigate } from "react-router-dom";
import {
  Zap, ArrowRight, Radar, Scale, TrendingUp, CalendarRange,
  MessageSquare, BarChart3,
} from "lucide-react";
import { useAuth } from "../state/auth";
import { useInView } from "../hooks/useInView";
import { ThemeToggle } from "../components/ThemeToggle";

const FEATURES = [
  {
    icon: Radar,
    title: "Waiver-wire radar",
    body: "Ranked pickups for your exact open spots, weighted by how many games each player has left this week.",
  },
  {
    icon: Scale,
    title: "Trade analysis",
    body: "Paste any offer and get an accept / counter / decline verdict with a category-by-category delta.",
  },
  {
    icon: TrendingUp,
    title: "Buy-low & sell-high",
    body: "Spot players whose value is about to swing before the rest of your league notices.",
  },
  {
    icon: CalendarRange,
    title: "Schedule-aware",
    body: "Knows your thin and heavy days, and which teams to stream against for the extra games.",
  },
];

const STEPS = [
  { n: "1", title: "Ask anything", body: "“Who should I start tonight?” — in plain language, like texting a sharp friend." },
  { n: "2", title: "Lightning digs in", body: "It pulls your roster, the wire, and the schedule, then reasons over your league's scoring." },
  { n: "3", title: "Make the move", body: "Clear recommendations backed by the numbers — no spreadsheets required." },
];

export function LandingView({ theme, onToggle }: { theme: string; onToggle: () => void }) {
  const { user, ready } = useAuth();
  const { ref: featuresRef, inView: featuresIn } = useInView<HTMLElement>();
  const { ref: stepsRef, inView: stepsIn } = useInView<HTMLElement>();
  const { ref: ctaRef, inView: ctaIn } = useInView<HTMLElement>();

  // Signed-in visitors go straight to the app.
  if (ready && user) return <Navigate to="/app" replace />;

  return (
    <div className="lp">
      <header className="lp-topbar">
        <div className="brand lp-logo">
          <span className="mark"><Zap fill="currentColor" /></span>Lightning
        </div>
        <div className="lp-topbar-right">
          <ThemeToggle theme={theme} onToggle={onToggle} />
          <Link to="/login" className="lp-nav-link">Sign in</Link>
          <Link to="/app" className="signin-btn">Open app</Link>
        </div>
      </header>

      <section className="lp-hero">
        <div className="lp-hero-copy">
          <span className="lp-eyebrow"><Zap size={13} fill="currentColor" /> Fantasy basketball, sharpened by AI</span>
          <h1 className="lp-title">Your fantasy GM, electrified.</h1>
          <p className="lp-sub">
            Waiver-wire radar, trade analysis, and buy-low targets — grounded in your
            league, delivered in plain language. Meet the assistant that actually reads
            the box scores for you.
          </p>
          <div className="lp-cta-row">
            <Link to="/app" className="lp-btn lp-btn-primary">
              Try the demo <ArrowRight size={17} />
            </Link>
            <Link to="/login" className="lp-btn lp-btn-ghost">Sign in</Link>
          </div>
          <p className="lp-note">No account needed — jump straight into a real-NBA demo league.</p>
        </div>

        <div className="lp-hero-visual" aria-hidden="true">
          <div className="hv-card hv-chat">
            <div className="hv-bubble hv-user">Who should I pick up this week?</div>
            <div className="hv-bubble hv-ai">
              <span className="hv-chip"><span className="hv-dot" /> scanning the waiver wire</span>
              <p>Grab <b>Josh Hart</b> — he has <b>4 games</b> this week and is trending up in
                boards + steals.</p>
            </div>
          </div>

          <div className="hv-card hv-board">
            <div className="hv-board-head"><BarChart3 size={14} /> Streaming board</div>
            <div className="hv-bar"><span className="hv-bar-label">J. Hart</span><span className="hv-track"><span className="hv-fill" style={{ width: "92%" }} /></span></div>
            <div className="hv-bar"><span className="hv-bar-label">D. Gafford</span><span className="hv-track"><span className="hv-fill" style={{ width: "74%" }} /></span></div>
            <div className="hv-bar"><span className="hv-bar-label">A. Simons</span><span className="hv-track"><span className="hv-fill" style={{ width: "58%" }} /></span></div>
          </div>

          <div className="hv-badge"><MessageSquare size={13} /> Accept trade</div>
        </div>
      </section>

      <section ref={featuresRef} className={"lp-section lp-features reveal" + (featuresIn ? " in" : "")}>
        <div className="lp-section-head">
          <h2>Everything a good GM does — in seconds</h2>
          <p>Four tools, one conversation. Lightning handles the grind so you make the calls.</p>
        </div>
        <div className="lp-grid">
          {FEATURES.map((f) => (
            <article key={f.title} className="lp-card">
              <span className="lp-card-icon"><f.icon size={20} /></span>
              <h3>{f.title}</h3>
              <p>{f.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section ref={stepsRef} className={"lp-section lp-steps reveal" + (stepsIn ? " in" : "")}>
        <div className="lp-section-head">
          <h2>How it works</h2>
        </div>
        <div className="lp-steps-grid">
          {STEPS.map((s) => (
            <div key={s.n} className="lp-step">
              <span className="lp-step-n">{s.n}</span>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section ref={ctaRef} className={"lp-section lp-cta reveal" + (ctaIn ? " in" : "")}>
        <div className="lp-cta-inner">
          <h2>Ready to run your team like a pro?</h2>
          <p>Start with the demo league — no sign-up, no credit card.</p>
          <div className="lp-cta-row">
            <Link to="/app" className="lp-btn lp-btn-primary">
              Open Lightning <ArrowRight size={17} />
            </Link>
            <Link to="/login" className="lp-btn lp-btn-ghost">Create an account</Link>
          </div>
        </div>
      </section>

      <footer className="lp-footer">
        <div className="brand lp-logo">
          <span className="mark"><Zap fill="currentColor" /></span>Lightning
        </div>
        <span className="lp-footer-note">Your fantasy GM, electrified.</span>
      </footer>
    </div>
  );
}
