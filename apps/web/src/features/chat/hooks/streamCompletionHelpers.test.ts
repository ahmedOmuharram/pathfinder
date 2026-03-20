// @vitest-environment jsdom
/**
 * Tests for streamCompletionHelpers — pure functions extracted from
 * useStreamEvents onComplete callback.
 */

import { describe, expect, it } from "vitest";
import type { Message, OptimizationProgressData } from "@pathfinder/shared";
import {
  persistReasoningToLastMessage,
  persistOptimizationDataToLastMessage,
} from "./streamCompletionHelpers";

const ts = "2026-01-01T00:00:00Z";

// ---------------------------------------------------------------------------
// persistReasoningToLastMessage
// ---------------------------------------------------------------------------

describe("persistReasoningToLastMessage", () => {
  it("returns prev unchanged when reasoning is null", () => {
    const prev: Message[] = [{ role: "assistant", content: "Hello", timestamp: ts }];
    const result = persistReasoningToLastMessage(prev, null);
    expect(result).toBe(prev); // referential equality — no change
  });

  it("attaches reasoning to the last assistant message", () => {
    const prev: Message[] = [
      { role: "user", content: "Hi", timestamp: ts },
      { role: "assistant", content: "Response", timestamp: ts },
    ];
    const result = persistReasoningToLastMessage(prev, "thinking...");
    expect(result).not.toBe(prev);
    expect(result[1]?.reasoning).toBe("thinking...");
    // User message untouched
    expect(result[0]).toBe(prev[0]);
  });

  it("skips if last assistant already has reasoning", () => {
    const prev: Message[] = [
      {
        role: "assistant",
        content: "Response",
        timestamp: ts,
        reasoning: "existing",
      },
    ];
    const result = persistReasoningToLastMessage(prev, "new reasoning");
    expect(result).toBe(prev); // no change
  });

  it("returns prev unchanged when no assistant messages exist", () => {
    const prev: Message[] = [{ role: "user", content: "Hi", timestamp: ts }];
    const result = persistReasoningToLastMessage(prev, "some reasoning");
    expect(result).toBe(prev);
  });
});

// ---------------------------------------------------------------------------
// persistOptimizationDataToLastMessage
// ---------------------------------------------------------------------------

describe("persistOptimizationDataToLastMessage", () => {
  it("returns prev unchanged when optimization data is null", () => {
    const prev: Message[] = [{ role: "assistant", content: "Done", timestamp: ts }];
    const result = persistOptimizationDataToLastMessage(prev, null);
    expect(result).toBe(prev);
  });

  it("attaches optimization data to the last assistant message", () => {
    const progress: OptimizationProgressData = {
      optimizationId: "opt-1",
      status: "running",
    };
    const prev: Message[] = [
      { role: "user", content: "Optimize", timestamp: ts },
      { role: "assistant", content: "Optimizing...", timestamp: ts },
    ];
    const result = persistOptimizationDataToLastMessage(prev, progress);
    expect(result).not.toBe(prev);
    expect(result[1]?.optimizationProgress).toBe(progress);
  });

  it("returns prev unchanged when no assistant messages exist", () => {
    const progress: OptimizationProgressData = {
      optimizationId: "opt-2",
      status: "complete",
    };
    const prev: Message[] = [{ role: "user", content: "Hi", timestamp: ts }];
    const result = persistOptimizationDataToLastMessage(prev, progress);
    expect(result).toBe(prev);
  });
});
