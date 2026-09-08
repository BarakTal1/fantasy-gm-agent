import { describe, it, expect, vi } from "vitest";
import { parseSSE } from "../lib/sse";

describe("parseSSE", () => {
  it("dispatches events with parsed data", () => {
    const events: Array<[string, any]> = [];
    const feed = parseSSE((ev, data) => events.push([ev, data]));
    feed('event: tool\ndata: {"name":"get_free_agents"}\n\n');
    feed('event: token\ndata: {"text":"Pick "}\n\nevent: token\ndata: {"text":"Hart"}\n\n');
    feed('event: done\ndata: {}\n\n');
    expect(events).toEqual([
      ["tool", { name: "get_free_agents" }],
      ["token", { text: "Pick " }],
      ["token", { text: "Hart" }],
      ["done", {}],
    ]);
  });
});
