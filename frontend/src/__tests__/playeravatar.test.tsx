import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PlayerAvatar } from "../components/PlayerAvatar";

describe("PlayerAvatar", () => {
  it("renders an image when image_url is present", () => {
    render(<PlayerAvatar name="Devin Booker" image_url="http://x/booker.png" />);
    const img = screen.getByRole("img", { name: /devin booker/i }) as HTMLImageElement;
    expect(img.src).toContain("booker.png");
  });

  it("falls back to initials when no url", () => {
    render(<PlayerAvatar name="Devin Booker" image_url={null} />);
    expect(screen.getByText("DB")).toBeInTheDocument();
  });

  it("falls back to initials when the image errors", () => {
    render(<PlayerAvatar name="Kevin Durant" image_url="http://x/broken.png" />);
    fireEvent.error(screen.getByRole("img", { name: /kevin durant/i }));
    expect(screen.getByText("KD")).toBeInTheDocument();
  });
});
