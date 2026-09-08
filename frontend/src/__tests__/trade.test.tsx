import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "../lib/api";
import { TradeView } from "../views/TradeView";

describe("TradeView", () => {
  it("picks players from rosters and shows a verdict", async () => {
    vi.spyOn(api, "getTeams").mockResolvedValue({
      my_team_key: "t1",
      teams: [
        { team_key: "t1", name: "Mine",
          players: [{ player_id: "1", name: "My Star", nba_team: "LAL", stats: {} }] },
        { team_key: "t2", name: "Rival",
          players: [{ player_id: "2", name: "Their Star", nba_team: "BOS", stats: {} }] },
      ],
    });
    vi.spyOn(api, "analyzeTrade").mockResolvedValue({
      format: "category", delta: { AST: -6 }, summary: { improved: [], worsened: ["AST"] },
      verdict: "You lose assists.", recommendation: "DECLINE",
    });
    render(<TradeView />);
    // select my player, opponent, their player via the pickers, then analyze
    await userEvent.click(await screen.findByRole("button", { name: /my star/i }));
    await userEvent.selectOptions(screen.getByLabelText(/opponent team/i), "t2");
    await userEvent.click(await screen.findByRole("button", { name: /their star/i }));
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(await screen.findByText(/DECLINE/)).toBeInTheDocument();
  });

  it("renders a points-league verdict as give/get/net fantasy points", async () => {
    vi.spyOn(api, "getTeams").mockResolvedValue({
      my_team_key: "t1",
      teams: [
        { team_key: "t1", name: "Mine",
          players: [{ player_id: "1", name: "My Star", nba_team: "LAL", stats: {} }] },
        { team_key: "t2", name: "Rival",
          players: [{ player_id: "2", name: "Their Star", nba_team: "BOS", stats: {} }] },
      ],
    });
    vi.spyOn(api, "analyzeTrade").mockResolvedValue({
      format: "points", delta: { give_value: 13, get_value: 20, net: 7 },
      verdict: "You gain value.", recommendation: "ACCEPT",
    });
    render(<TradeView />);
    await userEvent.click(await screen.findByRole("button", { name: /my star/i }));
    await userEvent.selectOptions(screen.getByLabelText(/opponent team/i), "t2");
    await userEvent.click(await screen.findByRole("button", { name: /their star/i }));
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(await screen.findByText(/ACCEPT/)).toBeInTheDocument();
    expect(screen.getByText(/net/i)).toBeInTheDocument();
    expect(screen.getByText("13")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument();
  });

  it("shows an error state with retry when rosters fail to load", async () => {
    vi.spyOn(api, "getTeams").mockRejectedValue(new Error("HTTP 500"));
    render(<TradeView />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/failed to load/i);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows an empty state prompting player selection before analyzing", async () => {
    vi.spyOn(api, "getTeams").mockResolvedValue({
      my_team_key: "t1",
      teams: [
        { team_key: "t1", name: "Mine", players: [] },
        { team_key: "t2", name: "Rival", players: [] },
      ],
    });
    render(<TradeView />);
    expect(await screen.findByText(/pick players to analyze/i)).toBeInTheDocument();
  });
});
