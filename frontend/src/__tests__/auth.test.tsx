import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import * as api from "../lib/api";
import { AuthProvider } from "../state/auth";
import { Header } from "../components/Header";
import { LoginView } from "../views/LoginView";

function renderWith(node: React.ReactNode, entries: string[] = ["/"]) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={entries}>{node}</MemoryRouter>
    </AuthProvider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(api, "getLeagueInfo").mockResolvedValue({ name: "Demo", format: "category", format_label: "9-cat" });
});

describe("auth", () => {
  it("Header shows a Sign in link to /login when logged out", async () => {
    vi.spyOn(api, "getMe").mockResolvedValue(null);
    renderWith(<Header theme="light" onToggle={() => {}} />);
    const link = await screen.findByRole("link", { name: /sign in/i });
    expect(link).toHaveAttribute("href", "/login");
  });

  it("logs in through the login page", async () => {
    vi.spyOn(api, "getMe").mockResolvedValue(null);
    vi.spyOn(api, "login").mockResolvedValue({ email: "me@x.com", league_format: "category" });
    renderWith(<LoginView theme="light" onToggle={() => {}} />, ["/login"]);

    await userEvent.type(screen.getByLabelText(/email/i), "me@x.com");
    await userEvent.type(screen.getByLabelText(/password/i), "secret1");
    await userEvent.click(screen.getByRole("button", { name: /^sign in$/i }));

    expect(api.login).toHaveBeenCalledWith("me@x.com", "secret1");
  });

  it("shows the account email when already signed in", async () => {
    vi.spyOn(api, "getMe").mockResolvedValue({ email: "you@x.com", league_format: "points" });
    renderWith(<Header theme="light" onToggle={() => {}} />);
    expect(await screen.findByText("you@x.com")).toBeInTheDocument();
  });
});
