import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import * as api from "../lib/api";
import { LeagueView } from "../views/LeagueView";

describe("LeagueView", () => {
  it("renders the teams table and buy-low/sell-high list", async () => {
    vi.spyOn(api, "getLeagueAnalytics").mockResolvedValue({
      format: "category",
      my_team_key: "t1",
      teams: [
        { team_key: "t1", name: "Mine",
          players: [{ player_id: "1", name: "A", nba_team: "LAL", stats: { PTS: 20 } }] },
        { team_key: "t2", name: "Rival",
          players: [{ player_id: "2", name: "B", nba_team: "BOS", stats: { PTS: 10 } }] },
      ],
      category_profile: { PTS: { you: 20, league_avg: 15 } },
      buy_low_sell_high: [
        { player_id: "2", name: "Cold Star", nba_team: "BOS", signal: "buy_low",
          strength: 0.6, efficiency_delta: -1.2, volume_delta: -0.1, confidence: 0.8,
          drivers: ["FG% below season"] }],
    });
    render(<LeagueView />);
    expect(await screen.findByText(/Mine/)).toBeInTheDocument();
    expect(screen.getAllByText(/Cold Star/).length).toBeGreaterThan(0);
    expect(screen.getByText(/FG% below season/)).toBeInTheDocument();
  });

  it("shows an error state with retry on failure", async () => {
    vi.spyOn(api, "getLeagueAnalytics").mockRejectedValue(new Error("HTTP 500"));
    render(<LeagueView />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/failed to load/i);
  });
});
