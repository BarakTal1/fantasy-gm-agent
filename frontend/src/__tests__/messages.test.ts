import { describe, it, expect } from "vitest";
import { chatReducer, initialState, type ChatAction } from "../state/messages";

function run(actions: ChatAction[]) {
  return actions.reduce(chatReducer, initialState);
}

describe("chatReducer", () => {
  it("adds a user message and opens an assistant turn", () => {
    const s = run([{ type: "send", text: "hi" }]);
    expect(s.messages[0]).toMatchObject({ role: "user", content: "hi" });
    expect(s.messages[1]).toMatchObject({ role: "assistant", streaming: true });
    expect(s.streaming).toBe(true);
  });
  it("records tool calls then streams tokens", () => {
    const s = run([
      { type: "send", text: "hi" },
      { type: "tool", name: "get_trends" },
      { type: "token", text: "Pick " },
      { type: "token", text: "Hart" },
      { type: "done" },
    ]);
    const a = s.messages[1];
    expect(a.tools).toEqual(["get_trends"]);
    expect(a.content).toBe("Pick Hart");
    expect(a.streaming).toBe(false);
    expect(s.streaming).toBe(false);
  });
  it("final replaces content when no tokens streamed", () => {
    const s = run([{ type: "send", text: "hi" }, { type: "final", text: "Answer" },
                   { type: "done" }]);
    expect(s.messages[1].content).toBe("Answer");
  });
  it("captures errors on the open assistant turn", () => {
    const s = run([{ type: "send", text: "hi" }, { type: "error", message: "boom" }]);
    expect(s.messages[1].error).toBe("boom");
    expect(s.streaming).toBe(false);
  });
});
