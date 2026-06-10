import { describe, expect, it } from "vitest";

import { computeRailActivity } from "./railActivity";

describe("computeRailActivity", () => {
  it("tallies per-panel data parts and detects a user message", () => {
    const activity = computeRailActivity([
      { role: "user", parts: [{ type: "text" }] },
      {
        role: "assistant",
        parts: [
          { type: "data-ledger-update" },
          { type: "data-ledger-update" },
          { type: "data-scratchpad-updated" },
          { type: "data-memory-retrieved" },
          { type: "text" },
        ],
      },
    ]);
    expect(activity.hasUserMessage).toBe(true);
    expect(activity.ledgerCount).toBe(2);
    expect(activity.scratchpadCount).toBe(1);
    expect(activity.memoryCount).toBe(1);
    expect(activity.taskCount).toBe(0);
  });

  it("reports no user message for an empty/assistant-only thread", () => {
    const activity = computeRailActivity([
      { role: "assistant", parts: [{ type: "data-ledger-update" }] },
    ]);
    expect(activity.hasUserMessage).toBe(false);
    expect(activity.ledgerCount).toBe(1);
  });
});
