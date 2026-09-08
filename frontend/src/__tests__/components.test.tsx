import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MessageBubble } from "../components/MessageBubble";
import { EmptyState } from "../components/EmptyState";
import { Composer } from "../components/Composer";

describe("components", () => {
  it("renders an assistant markdown table", () => {
    render(<MessageBubble m={{ role: "assistant",
      content: "| P | AST |\n|---|---|\n| Hart | 5.2 |" }} />);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("Hart")).toBeInTheDocument();
  });
  it("empty state fires an example prompt", async () => {
    const onPick = vi.fn();
    render(<EmptyState onPick={onPick} />);
    await userEvent.click(screen.getByText(/who should i pick up/i));
    expect(onPick).toHaveBeenCalled();
  });
  it("composer submits on send", async () => {
    const onSend = vi.fn();
    render(<Composer streaming={false} onSend={onSend} onStop={() => {}} />);
    await userEvent.type(screen.getByRole("textbox"), "hello");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    expect(onSend).toHaveBeenCalledWith("hello");
  });
});
