import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTheme } from "../hooks/useTheme";

beforeEach(() => { localStorage.clear(); document.documentElement.removeAttribute("data-theme"); });

describe("useTheme", () => {
  it("toggles and persists", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current.toggle());
    const t = result.current.theme;
    expect(["light", "dark"]).toContain(t);
    expect(document.documentElement.getAttribute("data-theme")).toBe(t);
    expect(localStorage.getItem("theme")).toBe(t);
  });
});
