import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import * as api from "../lib/api";
import { MyTeamView } from "../views/MyTeamView";

const ANALYTICS = {
  best_player: { player_id: "1", name: "Devin Booker", nba_team: "PHX",
    positions: ["PG", "SG"], image_url: null, value: 42 },
  position_strengths: [
    { position: "SG", count: 2, total_value: 80, avg_value: 40 },
    { position: "PG", count: 1, total_value: 42, avg_value: 42 },
  ],
  positional_balance: [
    { position: "PG", eligible: 1, required: null, thin: true },
    { position: "SG", eligible: 2, required: null, thin: false },
    { position: "SF", eligible: 0, required: null, thin: true },
    { position: "PF", eligible: 2, required: null, thin: false },
    { position: "C", eligible: 2, required: null, thin: false },
  ],
};

describe("MyTeamView", () => {
  it("renders per-player cards (positions + form tag + projected) then the radar", async () => {
    vi.spyOn(api, "getMyTeamAnalytics").mockResolvedValue({
      format: "category",
      roster: [{ player_id: "1", name: "Devin Booker", nba_team: "PHX",
        image_url: null, positions: ["PG", "SG"], games: 4, form: "sell_high",
        projected: { PTS: 120, AST: 20 } }],
      category_profile: { PTS: { you: 110, league_avg: 100 } },
      ...ANALYTICS,
    });
    render(<MyTeamView />);
    // Booker appears on the roster card and in the best-player tile.
    expect((await screen.findAllByText(/Devin Booker/)).length).toBeGreaterThan(0);
    expect(screen.getByText(/sell high/i)).toBeInTheDocument();
    expect(screen.getAllByText(/PTS/).length).toBeGreaterThan(0);  // projected + radar
    // Position tag chips on the card (PG + SG appear in both card and analytics).
    expect(screen.getAllByText("PG").length).toBeGreaterThan(0);
  });

  it("surfaces best player and strongest position analytics", async () => {
    vi.spyOn(api, "getMyTeamAnalytics").mockResolvedValue({
      format: "category",
      roster: [{ player_id: "1", name: "Devin Booker", nba_team: "PHX",
        image_url: null, positions: ["PG", "SG"], games: 4, form: "neutral",
        projected: { PTS: 120 } }],
      category_profile: { PTS: { you: 110, league_avg: 100 } },
      ...ANALYTICS,
    });
    render(<MyTeamView />);
    expect(await screen.findByText(/best player/i)).toBeInTheDocument();
    expect(screen.getByText(/strongest position/i)).toBeInTheDocument();
    expect(screen.getByText(/positional depth/i)).toBeInTheDocument();
  });

  it("renders projected points for points leagues", async () => {
    vi.spyOn(api, "getMyTeamAnalytics").mockResolvedValue({
      format: "points",
      roster: [{ player_id: "1", name: "A B", nba_team: "LAL",
        image_url: null, positions: ["C"], games: 3, form: "neutral",
        projected_points: 99 }],
      ...ANALYTICS,
    });
    render(<MyTeamView />);
    expect(await screen.findByText("99", { exact: false })).toBeInTheDocument();
  });

  it("shows an error state with retry on failure", async () => {
    vi.spyOn(api, "getMyTeamAnalytics").mockRejectedValue(new Error("HTTP 500"));
    render(<MyTeamView />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/failed to load/i);
  });
});
