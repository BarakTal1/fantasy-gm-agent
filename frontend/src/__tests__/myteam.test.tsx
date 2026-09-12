import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import * as api from "../lib/api";
import { MyTeamView } from "../views/MyTeamView";

describe("MyTeamView", () => {
  it("renders my category profile and weekday coverage", async () => {
    vi.spyOn(api, "getMyTeamAnalytics").mockResolvedValue({
      format: "category",
      weekdays: [{ day: "Mon", count: 5, weak: false }, { day: "Tue", count: 2, weak: true }],
      category_profile: { PTS: { you: 110, league_avg: 100 }, AST: { you: 20, league_avg: 25 } },
    });
    render(<MyTeamView />);
    expect((await screen.findAllByText(/PTS/)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Mon/).length).toBeGreaterThan(0);
  });

  it("shows an error state with retry on failure", async () => {
    vi.spyOn(api, "getMyTeamAnalytics").mockRejectedValue(new Error("HTTP 500"));
    render(<MyTeamView />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/failed to load/i);
  });
});
