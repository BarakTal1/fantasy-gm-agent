import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import * as api from "../lib/api";
import { MyTeamView } from "../views/MyTeamView";

describe("MyTeamView", () => {
  it("renders per-player cards (form tag + projected) then the radar", async () => {
    vi.spyOn(api, "getMyTeamAnalytics").mockResolvedValue({
      format: "category",
      roster: [{ player_id: "1", name: "Devin Booker", nba_team: "PHX",
        image_url: null, games: 4, form: "sell_high", projected: { PTS: 120, AST: 20 } }],
      category_profile: { PTS: { you: 110, league_avg: 100 } },
    });
    render(<MyTeamView />);
    expect(await screen.findByText(/Devin Booker/)).toBeInTheDocument();
    expect(screen.getByText(/sell high/i)).toBeInTheDocument();
    expect(screen.getAllByText(/PTS/).length).toBeGreaterThan(0);  // projected + radar
  });

  it("renders projected points for points leagues", async () => {
    vi.spyOn(api, "getMyTeamAnalytics").mockResolvedValue({
      format: "points",
      roster: [{ player_id: "1", name: "A B", nba_team: "LAL",
        image_url: null, games: 3, form: "neutral", projected_points: 99 }],
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
