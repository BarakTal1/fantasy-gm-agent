import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Nav } from "../components/Nav";

describe("Nav", () => {
  it("renders three tabs with the active one marked", () => {
    render(<MemoryRouter initialEntries={["/dashboard"]}><Nav /></MemoryRouter>);
    expect(screen.getByRole("link", { name: /chat/i })).toBeInTheDocument();
    const dash = screen.getByRole("link", { name: /dashboard/i });
    expect(dash).toHaveAttribute("aria-current", "page");
  });
});
