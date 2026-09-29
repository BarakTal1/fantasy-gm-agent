import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import * as api from "../lib/api";
import { AuthProvider } from "../state/auth";
import { SettingsView } from "../views/SettingsView";

const CONFIG: api.LeagueConfig = {
  name: "Dubs Dynasty",
  format: "category",
  categories: ["PTS", "REB", "AST"],
  point_weights: {},
  roster_slots: { PG: 2, C: 1 },
  source: "demo",
  yahoo_connected: false,
  options: {
    categories: ["FG%", "FT%", "3PTM", "PTS", "REB", "AST", "ST", "BLK", "TO"],
    point_stats: ["PTS", "REB", "AST", "3PTM", "ST", "BLK", "TO"],
    positions: ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"],
  },
};

function renderSettings() {
  return render(
    <AuthProvider>
      <MemoryRouter><SettingsView theme="light" onToggle={() => {}} /></MemoryRouter>
    </AuthProvider>,
  );
}

beforeEach(() => vi.restoreAllMocks());

describe("SettingsView", () => {
  it("loads and saves a manual league config for a signed-in user", async () => {
    vi.spyOn(api, "getMe").mockResolvedValue({ email: "a@b.com", league_format: "category" });
    vi.spyOn(api, "getLeagueConfig").mockResolvedValue(CONFIG);
    const save = vi.spyOn(api, "saveLeagueConfig")
      .mockResolvedValue({ ...CONFIG, source: "manual", categories: ["PTS", "REB", "AST", "BLK"] });
    renderSettings();

    // League name hydrated from the loaded config.
    expect(await screen.findByDisplayValue("Dubs Dynasty")).toBeInTheDocument();

    // Toggle a category on, then save.
    await userEvent.click(screen.getByRole("button", { name: "BLK" }));
    await userEvent.click(screen.getByRole("button", { name: /save league settings/i }));

    expect(save).toHaveBeenCalledTimes(1);
    const arg = save.mock.calls[0][0];
    expect(arg.format).toBe("category");
    expect(arg.categories).toContain("BLK");
    expect(await screen.findByText(/league settings saved/i)).toBeInTheDocument();
  });

  it("shows the not-connected Yahoo fallback message on sync", async () => {
    vi.spyOn(api, "getMe").mockResolvedValue({ email: "a@b.com", league_format: "category" });
    vi.spyOn(api, "getLeagueConfig").mockResolvedValue(CONFIG);
    vi.spyOn(api, "syncLeagueFromYahoo")
      .mockRejectedValue(new Error("Yahoo isn't connected yet — access is pending."));
    renderSettings();

    await screen.findByDisplayValue("Dubs Dynasty");
    await userEvent.click(screen.getByRole("button", { name: /sync from yahoo/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/connected/i);
  });

  it("prompts to sign in when logged out", async () => {
    vi.spyOn(api, "getMe").mockResolvedValue(null);
    renderSettings();
    expect(await screen.findByText(/sign in to set up your league/i)).toBeInTheDocument();
  });

  it("switches to point weights for a points-format config", async () => {
    vi.spyOn(api, "getMe").mockResolvedValue({ email: "a@b.com", league_format: "points" });
    vi.spyOn(api, "getLeagueConfig").mockResolvedValue({
      ...CONFIG, format: "points", categories: [],
      point_weights: { PTS: 1, REB: 1.2, AST: 1.5 },
    });
    renderSettings();
    await screen.findByDisplayValue("Dubs Dynasty");
    await waitFor(() => expect(screen.getByText(/point weights/i)).toBeInTheDocument());
    // Points weight input is present and hydrated.
    expect(screen.getByDisplayValue("1.5")).toBeInTheDocument();
  });
});
