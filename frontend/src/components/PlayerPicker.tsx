import type { Player } from "../lib/api";

export function PlayerPicker({ label, players, selected, onToggle }: {
  label: string;
  players: Player[];
  selected: string[];
  onToggle: (playerId: string) => void;
}) {
  return (
    <div className="player-picker">
      <span className="picker-label">{label}</span>
      {players.length === 0 ? (
        <p className="picker-empty">No players on this roster.</p>
      ) : (
        <div className="picker-list">
          {players.map((p) => {
            const isSelected = selected.includes(p.player_id);
            return (
              <button
                key={p.player_id}
                type="button"
                className={"picker-btn" + (isSelected ? " selected" : "")}
                aria-pressed={isSelected}
                onClick={() => onToggle(p.player_id)}
              >
                {p.name}
                <em>{p.nba_team}</em>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
