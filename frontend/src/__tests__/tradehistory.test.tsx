import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "../lib/api";
import { TradeHistoryView } from "../views/TradeHistoryView";

beforeEach(() => vi.restoreAllMocks());

describe("TradeHistoryView", () => {
  it("renders a trade and expands a player's before/after", async () => {
    vi.spyOn(api, "getTradeHistory").mockResolvedValue({
      trades: [{
        date: "2025-12-14", with_team: "Team 4",
        gave: [{ player_id: "1", name: "RJ Barrett", nba_team: "TOR",
                 before: { PTS: 20 }, after: { PTS: 18 } }],
        got: [{ player_id: "2", name: "De'Aaron Fox", nba_team: "SAS",
                before: { PTS: 25 }, after: { PTS: 28 } }],
      }],
    });
    render(<TradeHistoryView />);

    expect(await screen.findByText("with Team 4")).toBeInTheDocument();
    const fox = screen.getByRole("button", { name: /de'aaron fox/i });
    expect(fox).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(fox);
    expect(fox).toHaveAttribute("aria-expanded", "true");
    // before (25) and after (28) both visible in the expanded table
    expect(screen.getByText("25")).toBeInTheDocument();
    expect(screen.getByText("28")).toBeInTheDocument();
  });

  it("shows an empty state with no trades", async () => {
    vi.spyOn(api, "getTradeHistory").mockResolvedValue({ trades: [] });
    render(<TradeHistoryView />);
    expect(await screen.findByText(/no trades yet/i)).toBeInTheDocument();
  });
});
