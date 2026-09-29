import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BarList } from "../components/charts/BarList";
import { DivergingList } from "../components/charts/DivergingList";

describe("charts", () => {
  it("BarList renders a labeled row per item with a table fallback", () => {
    render(<BarList title="Streaming" items={[
      { label: "Josh Hart", value: 54, sub: "NYK · 4 gm" }]} />);
    expect(screen.getByText("Josh Hart")).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
  });
  it("DivergingList colors buy-low vs sell-high", () => {
    render(<DivergingList items={[{ label: "X", value: -22, signal: "buy_low" }]} />);
    expect(screen.getByText(/buy low/i)).toBeInTheDocument();
  });
});
