import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import * as api from "../lib/api";
import { DashboardView } from "../views/DashboardView";

describe("DashboardView", () => {
  it("renders the four sections from the payload", async () => {
    vi.spyOn(api, "getDashboard").mockResolvedValue({
      category_profile: { PTS: { you: 20, league_avg: 15 } },
      streaming_board: [{ player_id: "1", name: "Josh Hart", nba_team: "NYK",
                          games: 4, projected: { PTS: 54 }, score: 54 }],
      buy_low_sell_high: [{ player_id: "2", name: "X", delta_pct: -22, signal: "buy_low" }],
      schedule: { NYK: 4 },
    });
    render(<DashboardView />);
    expect(await screen.findByText("Josh Hart")).toBeInTheDocument();
    expect(screen.getByText(/category profile/i)).toBeInTheDocument();
  });
});
