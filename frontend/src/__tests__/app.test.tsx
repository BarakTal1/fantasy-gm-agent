import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";

function streamResponse(frames: string[]) {
  const enc = new TextEncoder();
  const body = new ReadableStream({
    start(c) { frames.forEach((f) => c.enqueue(enc.encode(f))); c.close(); },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

beforeEach(() => { localStorage.clear(); });

describe("App", () => {
  it("sends a message and renders the streamed answer", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(streamResponse([
      'event: tool\ndata: {"name":"get_free_agents"}\n\n',
      'event: token\ndata: {"text":"Add "}\n\n',
      'event: token\ndata: {"text":"Josh Hart."}\n\n',
      'event: done\ndata: {}\n\n',
    ]));
    render(<App />);
    await userEvent.type(screen.getByRole("textbox"), "who do I add?");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    expect(await screen.findByText(/Add Josh Hart\./)).toBeInTheDocument();
    expect(screen.getByText(/scanning the waiver wire/i)).toBeInTheDocument();
  });
});
