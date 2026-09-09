import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { TradedPlayer } from "../lib/api";

function fmt(n: number) {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

export function TradePlayerRow({ player, side }: { player: TradedPlayer; side: "gave" | "got" }) {
  const [open, setOpen] = useState(false);
  const stats = Object.keys(player.before);

  return (
    <div className={"tph-player " + side}>
      <button className="tph-toggle" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="tph-name">{player.name}</span>
        <span className="tph-team">{player.nba_team}</span>
      </button>
      {open && (
        <table className="tph-stats">
          <thead>
            <tr><th>Stat</th><th>Before</th><th>Since</th><th>Δ</th></tr>
          </thead>
          <tbody>
            {stats.map((k) => {
              const b = player.before[k];
              const a = player.after[k] ?? b;
              const d = a - b;
              const dir = d > 0.05 ? "up" : d < -0.05 ? "down" : "flat";
              const arrow = dir === "up" ? "▲" : dir === "down" ? "▼" : "–";
              return (
                <tr key={k}>
                  <td>{k}</td>
                  <td>{fmt(b)}</td>
                  <td>{fmt(a)}</td>
                  <td className={"delta-" + dir}>{arrow} {fmt(Math.abs(d))}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
