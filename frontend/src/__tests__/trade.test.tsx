import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "../lib/api";
import { TradeView } from "../views/TradeView";

describe("TradeView", () => {
  beforeEach(() => {
    vi.spyOn(api, "getReceivedTrades").mockResolvedValue({ offers: [] });
    vi.spyOn(api, "getTradeSuggestions").mockResolvedValue({ format: "category", suggestions: [] });
    vi.spyOn(api, "getTradeHistory").mockResolvedValue({ trades: [] });
  });

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

  it("lists received offers with an Analyze button", async () => {
    vi.spyOn(api, "getTeams").mockResolvedValue({
      my_team_key: "t1", teams: [{ team_key: "t1", name: "Mine", players: [] }],
    });
    vi.spyOn(api, "getReceivedTrades").mockResolvedValue({
      offers: [{ from_team: "Team 2", date: "2026-01-20", note: "swap",
        they_give: [{ player_id: "2", name: "Kyrie", nba_team: "DAL", stats: {} }],
        they_want: [{ player_id: "1", name: "Booker", nba_team: "PHX", stats: {} }] }],
    });
    render(<TradeView />);
    expect(await screen.findByText(/Team 2/)).toBeInTheDocument();
    expect(screen.getByText(/Kyrie/)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /analyze/i }).length).toBeGreaterThan(0);
  });

  it("lists suggested trades with targeted categories", async () => {
    vi.spyOn(api, "getTeams").mockResolvedValue({
      my_team_key: "t1", teams: [{ team_key: "t1", name: "Mine", players: [] }],
    });
    vi.spyOn(api, "getTradeSuggestions").mockResolvedValue({
      format: "category",
      suggestions: [{ with_team: "Rival",
        give: [{ player_id: "1", name: "My Star", nba_team: "LAL", stats: {} }],
        get: [{ player_id: "2", name: "Their Dimer", nba_team: "BOS", stats: {} }],
        targeted_categories: ["AST"], fairness_gap: 3.2, need_fit: 12.5 }],
    });
    render(<TradeView />);
    expect(await screen.findByText(/Their Dimer/)).toBeInTheDocument();
    expect(screen.getByText(/AST/)).toBeInTheDocument();
  });
});
