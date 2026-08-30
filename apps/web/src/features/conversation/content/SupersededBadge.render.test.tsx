/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const state = {
  message: {
    role: "assistant",
    content: [{ type: "data-strategy-revision", data: { revision: "rev-1" } }],
  },
  thread: {
    messages: [
      {
        role: "assistant",
        content: [{ type: "data-strategy-revision", data: { revision: "rev-2" } }],
      },
    ],
  },
};

vi.mock("@assistant-ui/react", () => ({
  useAuiState: (select: (s: typeof state) => unknown) => select(state),
}));

import { SupersededBadge } from "./SupersededBadge";

describe("SupersededBadge chrome", () => {
  it("marks the turn superseded when the strategy moved on", () => {
    render(<SupersededBadge />);
    const badge = screen.getByTestId("superseded-badge");
    expect(badge).toHaveTextContent("Superseded");
    expect(badge).toHaveTextContent("strategy changed since this answer");
  });

  it("carries the warning token, never a hardcoded amber", () => {
    render(<SupersededBadge />);
    const tokens = screen.getByTestId("superseded-badge").className.split(/\s+/);
    expect(tokens).toContain("text-warning");
    expect(tokens.filter((t) => t.includes("amber") || t.startsWith("dark:"))).toEqual(
      [],
    );
  });

  it("is a line of text, never a bordered pill", () => {
    render(<SupersededBadge />);
    const tokens = screen.getByTestId("superseded-badge").className.split(/\s+/);
    expect(
      tokens.filter(
        (t) => t === "border" || t.startsWith("border-") || t === "rounded-full",
      ),
    ).toEqual([]);
  });
});
