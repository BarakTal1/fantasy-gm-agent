import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import * as api from "../lib/api";
import { DashboardView } from "../views/DashboardView";

describe("DashboardView", () => {
  it("renders the category-league sections, including the radar", async () => {
    vi.spyOn(api, "getDashboard").mockResolvedValue({
      format: "category",
      schedule: { NYK: 4 },
      category_profile: { PTS: { you: 20, league_avg: 15 } },
      streaming_board: [{ player_id: "1", name: "Josh Hart", nba_team: "NYK",
                          games: 4, projected: { PTS: 54 }, score: 54 }],
      buy_low_sell_high: [{ player_id: "2", name: "X", delta_pct: -22, signal: "buy_low" }],
      recommended_pickups: [{ player_id: "3", name: "Add Me", nba_team: "BOS", games: 3,
                              score: 12, drop: { player_id: "9", name: "Drop Me", value: 2 } }],
    });
    render(<DashboardView />);
    expect((await screen.findAllByText("Josh Hart")).length).toBeGreaterThan(0);
    expect(screen.getByRole("img", { name: /category strengths versus the league average/i }))
      .toBeInTheDocument();
  });

  it("renders the points-league value board and not the radar", async () => {
    vi.spyOn(api, "getDashboard").mockResolvedValue({
      format: "points",
      schedule: { NYK: 4 },
      buy_low_sell_high: [],
      recommended_pickups: [{ player_id: "3", name: "Add Me", nba_team: "BOS", games: 3,
                              score: 12, drop: { player_id: "9", name: "Drop Me", value: 2 } }],
      points_value_board: [{ player_id: "1", name: "Points Guy", nba_team: "NYK",
                             games: 4, projected_points: 80 }],
    });
    render(<DashboardView />);
    expect((await screen.findAllByText("Points Guy")).length).toBeGreaterThan(0);
    expect(screen.queryByRole("img", { name: /category strengths versus the league average/i }))
      .not.toBeInTheDocument();
  });

  it("shows a recommended pickup's suggested drop", async () => {
    vi.spyOn(api, "getDashboard").mockResolvedValue({
      format: "points",
      schedule: {},
      buy_low_sell_high: [],
      recommended_pickups: [{ player_id: "3", name: "Add Me", nba_team: "BOS", games: 3,
                              score: 12, drop: { player_id: "9", name: "Drop Me", value: 2 } }],
      points_value_board: [],
    });
    render(<DashboardView />);
    expect((await screen.findAllByText("Add Me")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/drop me/i).length).toBeGreaterThan(0);
  });

  it("shows an error state with retry on failure", async () => {
    vi.spyOn(api, "getDashboard").mockRejectedValue(new Error("HTTP 500"));
    render(<DashboardView />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/failed to load/i);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("renders the weekday coverage card with a thin-day hint", async () => {
    vi.spyOn(api, "getDashboard").mockResolvedValue({
      format: "points", schedule: {}, buy_low_sell_high: [],
      recommended_pickups: [{ player_id: "3", name: "Add Me", nba_team: "BOS", games: 3,
                              score: 12, drop: null }],
      points_value_board: [],
    });
    vi.spyOn(api, "getWeekdays").mockResolvedValue({ days: [
      { day: "Mon", count: 6, weak: false }, { day: "Tue", count: 5, weak: false },
      { day: "Wed", count: 1, weak: true }, { day: "Thu", count: 5, weak: false },
      { day: "Fri", count: 5, weak: false }, { day: "Sat", count: 5, weak: false },
      { day: "Sun", count: 1, weak: true },
    ] });
    render(<DashboardView />);
    expect(await screen.findByText(/games this week by day/i)).toBeInTheDocument();
    expect(screen.getByText(/thin on Wed & Sun/i)).toBeInTheDocument();
  });

  it("shows an empty state when there are no recommendations", async () => {
    vi.spyOn(api, "getDashboard").mockResolvedValue({
      format: "points",
      schedule: {},
      buy_low_sell_high: [],
      recommended_pickups: [],
      points_value_board: [],
    });
    render(<DashboardView />);
    expect(await screen.findByText(/no recommendations/i)).toBeInTheDocument();
  });
});
