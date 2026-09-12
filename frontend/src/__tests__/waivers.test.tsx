import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import * as api from "../lib/api";
import { WaiversView } from "../views/WaiversView";

describe("WaiversView", () => {
  it("renders recommended pickups and the streaming board (category)", async () => {
    vi.spyOn(api, "getWaiversAnalytics").mockResolvedValue({
      format: "category",
      schedule: { LAL: 4 },
      recommended_pickups: [
        { player_id: "1", name: "Add Me", nba_team: "LAL", games: 4, score: 80,
          drop: { player_id: "9", name: "Drop Me", value: 5 } }],
      streaming_board: [
        { player_id: "2", name: "Streamer", nba_team: "LAL", games: 4,
          projected: { PTS: 40 }, score: 40 }],
      weekdays: [],
      teams_to_target: [],
    });
    render(<WaiversView />);
    expect((await screen.findAllByText(/Add Me/)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Streaming board/i).length).toBeGreaterThan(0);
  });

  it("shows an empty state when there are no recommendations", async () => {
    vi.spyOn(api, "getWaiversAnalytics").mockResolvedValue({
      format: "category", schedule: {}, recommended_pickups: [], streaming_board: [],
      weekdays: [], teams_to_target: [],
    });
    render(<WaiversView />);
    expect(await screen.findByText(/no recommendations/i)).toBeInTheDocument();
  });

  it("renders weekday coverage and teams to target", async () => {
    vi.spyOn(api, "getWaiversAnalytics").mockResolvedValue({
      format: "category", schedule: { PHX: 4 }, recommended_pickups: [], streaming_board: [],
      weekdays: [{ day: "Wed", count: 3, weak: true, heavy: false },
                 { day: "Fri", count: 3, weak: true, heavy: false }],
      teams_to_target: [{ nba_team: "PHX", weak_days: ["Wed", "Fri"],
        free_agents: [{ player_id: "f1", name: "Sun Guy", nba_team: "PHX", image_url: null }] }],
    });
    render(<WaiversView />);
    expect(await screen.findByText(/Teams to target/i)).toBeInTheDocument();
    expect(screen.getByText(/Sun Guy/)).toBeInTheDocument();
    expect(screen.getAllByText(/PHX/).length).toBeGreaterThan(0);
  });
});
