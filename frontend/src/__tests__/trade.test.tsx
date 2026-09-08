import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "../lib/api";
import { TradeView } from "../views/TradeView";

describe("TradeView", () => {
  it("analyzes a trade and shows the verdict + deltas", async () => {
    vi.spyOn(api, "analyzeTrade").mockResolvedValue({
      delta: { AST: -6 }, summary: { improved: [], worsened: ["AST"] },
      verdict: "Decline — you lose assists. DECLINE", recommendation: "DECLINE",
    });
    render(<TradeView />);
    await userEvent.type(screen.getByLabelText(/players to give/i), "1");
    await userEvent.type(screen.getByLabelText(/players to get/i), "2");
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(await screen.findByText(/DECLINE/)).toBeInTheDocument();
    expect(screen.getByText(/AST/)).toBeInTheDocument();
  });
});
