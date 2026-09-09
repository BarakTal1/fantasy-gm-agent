import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import * as api from "../lib/api";
import { AuthProvider } from "../state/auth";
import { Header } from "../components/Header";

function renderHeader() {
  return render(
    <AuthProvider>
      <MemoryRouter><Header theme="light" onToggle={() => {}} /></MemoryRouter>
    </AuthProvider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(api, "getLeagueInfo").mockResolvedValue({ name: "Demo", format: "category", format_label: "9-cat" });
});

describe("auth", () => {
  it("shows Sign in when logged out and logs in through the modal", async () => {
    vi.spyOn(api, "getMe").mockResolvedValue(null);
    vi.spyOn(api, "login").mockResolvedValue({ email: "me@x.com", league_format: "category" });
    renderHeader();

    const signIn = await screen.findByRole("button", { name: /sign in/i });
    await userEvent.click(signIn);
    await userEvent.type(screen.getByLabelText(/email/i), "me@x.com");
    await userEvent.type(screen.getByLabelText(/password/i), "secret1");
    await userEvent.click(screen.getByRole("button", { name: /^sign in$/i }));

    expect(await screen.findByText("me@x.com")).toBeInTheDocument();
    expect(api.login).toHaveBeenCalledWith("me@x.com", "secret1");
  });

  it("shows the account email when already signed in", async () => {
    vi.spyOn(api, "getMe").mockResolvedValue({ email: "you@x.com", league_format: "points" });
    renderHeader();
    expect(await screen.findByText("you@x.com")).toBeInTheDocument();
  });
});
