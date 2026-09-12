import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WeekdayBars } from "../components/charts/WeekdayBars";

describe("WeekdayBars", () => {
  it("flags thin and overloaded days", () => {
    render(<WeekdayBars days={[
      { day: "Mon", count: 12, weak: false, heavy: true },
      { day: "Tue", count: 2, weak: true, heavy: false },
      { day: "Wed", count: 6, weak: false, heavy: false },
    ]} />);
    expect(screen.getAllByText(/stream/i).length).toBeGreaterThan(0);       // thin Tue
    expect(screen.getAllByText(/waste|overloaded|10\+/i).length).toBeGreaterThan(0); // heavy Mon
  });
});
