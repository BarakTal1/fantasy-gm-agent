import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Nav } from "../components/Nav";

describe("Nav", () => {
  it("renders the five tabs with the active one marked", () => {
    render(<MemoryRouter initialEntries={["/my-team"]}><Nav /></MemoryRouter>);
    for (const label of [/chat/i, /my team/i, /waivers/i, /trade/i, /league/i]) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
    expect(screen.getByRole("link", { name: /my team/i })).toHaveAttribute("aria-current", "page");
  });
});
