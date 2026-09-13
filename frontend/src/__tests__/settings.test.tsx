import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import * as api from "../lib/api";
import { AuthProvider } from "../state/auth";
import { SettingsView } from "../views/SettingsView";

function renderSettings() {
  return render(
    <AuthProvider>
      <MemoryRouter><SettingsView theme="light" onToggle={() => {}} /></MemoryRouter>
    </AuthProvider>,
  );
}

beforeEach(() => vi.restoreAllMocks());

describe("SettingsView", () => {
  it("changes the league format for a signed-in user", async () => {
    vi.spyOn(api, "getMe").mockResolvedValue({ email: "a@b.com", league_format: "category" });
    const patch = vi.spyOn(api, "updateSettings").mockResolvedValue({ league_format: "points" });
    renderSettings();

    const pointsBtn = await screen.findByRole("radio", { name: /points/i });
    await userEvent.click(pointsBtn);
    expect(patch).toHaveBeenCalledWith("points");
    expect(await screen.findByRole("radio", { name: /points/i })).toHaveAttribute("aria-checked", "true");
  });

  it("prompts to sign in when logged out", async () => {
    vi.spyOn(api, "getMe").mockResolvedValue(null);
    renderSettings();
    expect(await screen.findByText(/sign in to choose your league/i)).toBeInTheDocument();
    expect(screen.getByText(/coming soon/i)).toBeInTheDocument();
  });
});
