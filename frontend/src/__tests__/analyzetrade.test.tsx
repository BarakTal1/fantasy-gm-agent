import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "../lib/api";
import { AnalyzeTrade } from "../components/AnalyzeTrade";

describe("AnalyzeTrade", () => {
  it("runs the Claude verdict on click and shows the recommendation", async () => {
    vi.spyOn(api, "analyzeTrade").mockResolvedValue({
      format: "category", delta: { AST: 6 }, summary: { improved: ["AST"], worsened: [] },
      verdict: "You gain assists. ACCEPT", recommendation: "ACCEPT",
    });
    render(<AnalyzeTrade give={["1"]} get={["2"]} />);
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(await screen.findByText(/ACCEPT/)).toBeInTheDocument();
    expect(screen.getByText(/You gain assists\./)).toBeInTheDocument();
  });

  it("shows an error if analysis fails", async () => {
    vi.spyOn(api, "analyzeTrade").mockRejectedValue(new Error("HTTP 429"));
    render(<AnalyzeTrade give={["1"]} get={["2"]} />);
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/failed to analyze/i);
  });
});
