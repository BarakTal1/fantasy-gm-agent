import { describe, it, expect } from "vitest";
import { toolMeta } from "../lib/toolMeta";

describe("toolMeta", () => {
  it("maps known tools to friendly labels", () => {
    expect(toolMeta("get_free_agents").label).toBe("Scanning the waiver wire");
    expect(toolMeta("get_weekly_schedule").label).toBe("Counting games this week");
    expect(toolMeta("get_trends").label).toBe("Analyzing recent form");
  });
  it("falls back for unknown tools", () => {
    expect(toolMeta("mystery").label).toBe("Working…");
  });
});
