/**
 * Regression tests for the retroactive modelId stamping fix in
 * `handleModelSelectedEvent`.
 *
 * Race scenario: `assistant_delta` can arrive on the SSE stream BEFORE
 * `model_selected` (subscription timing / operation recovery).  If the
 * message is created without a modelId, the fix stamps it retroactively
 * when the `model_selected` event finally lands.
 *
 * These tests lock in that behavior and verify edge cases.
 */

import { describe, it, expect, vi } from "vitest";
import type { Message, ModelSelectedData, PipelineConfig } from "@pathfinder/shared";
import { handleModelSelectedEvent } from "./handleChatEvent.messageMetadataEvents";
import { makeCtx } from "./handleChatEvent.testUtils";

const PIPELINE: PipelineConfig = {
  scoping: { modelId: "claude-sonnet-4-20250514", reasoningEffort: "low" },
  discovery: { modelId: "claude-sonnet-4-20250514", reasoningEffort: "medium" },
  planning: { modelId: "gpt-4", reasoningEffort: "high" },
  execution: { modelId: "claude-sonnet-4-20250514", reasoningEffort: "medium" },
  verification: { modelId: "claude-sonnet-4-20250514", reasoningEffort: "low" },
};

function modelSelectedData(pipeline: PipelineConfig): ModelSelectedData {
  return { pipeline };
}

describe("handleModelSelectedEvent — retroactive modelId stamping", () => {
  it("retroactively stamps modelId on assistant messages created before model_selected", () => {
    const { ctx } = makeCtx();
    const setMessagesSpy = vi.spyOn(ctx, "setMessages");

    const initial: Message[] = [
      {
        role: "user",
        content: "hello",
        timestamp: "2026-01-01T00:00:00.000Z",
      },
      {
        role: "assistant",
        content: "hi",
        modelId: null,
        timestamp: "2026-01-01T00:00:01.000Z",
      },
    ];

    // Capture the updater that handler passes to setMessages.
    let applied: Message[] | null = null;
    setMessagesSpy.mockImplementation((updater) => {
      if (typeof updater === "function") {
        applied = updater(initial);
      } else {
        applied = updater;
      }
    });

    handleModelSelectedEvent(ctx, modelSelectedData(PIPELINE));

    expect(setMessagesSpy).toHaveBeenCalled();
    expect(applied).not.toBeNull();
    expect(applied!).toHaveLength(2);
    expect(applied![0]?.role).toBe("user");
    expect(applied![1]?.role).toBe("assistant");
    // The assistant message must now carry the planning modelId.
    const stamped = applied![1];
    if (stamped?.role !== "assistant") {
      throw new Error("expected assistant message at index 1");
    }
    expect(stamped.modelId).toBe("gpt-4");
  });

  it("does NOT overwrite a non-empty existing modelId on existing assistant messages", () => {
    const { ctx } = makeCtx();
    const setMessagesSpy = vi.spyOn(ctx, "setMessages");

    const initial: Message[] = [
      {
        role: "user",
        content: "hello",
        timestamp: "2026-01-01T00:00:00.000Z",
      },
      {
        role: "assistant",
        content: "hi",
        modelId: "claude-3",
        timestamp: "2026-01-01T00:00:01.000Z",
      },
    ];

    let applied: Message[] = initial;
    setMessagesSpy.mockImplementation((updater) => {
      if (typeof updater === "function") {
        applied = updater(initial);
      } else {
        applied = updater;
      }
    });

    handleModelSelectedEvent(ctx, modelSelectedData(PIPELINE));

    // Setter may be called with a functional updater, but the resulting
    // messages array must leave messages[1].modelId unchanged.
    const stamped = applied[1];
    if (stamped?.role !== "assistant") {
      throw new Error("expected assistant at index 1");
    }
    expect(stamped.modelId).toBe("claude-3");
  });

  it("is a no-op on the messages array when no assistant message needs stamping", () => {
    const { ctx } = makeCtx();
    const setMessagesSpy = vi.spyOn(ctx, "setMessages");

    const initial: Message[] = [
      {
        role: "user",
        content: "hello",
        timestamp: "2026-01-01T00:00:00.000Z",
      },
      {
        role: "assistant",
        content: "hi",
        modelId: "claude-3",
        timestamp: "2026-01-01T00:00:01.000Z",
      },
    ];

    let applied: Message[] = initial;
    setMessagesSpy.mockImplementation((updater) => {
      if (typeof updater === "function") {
        applied = updater(initial);
      } else {
        applied = updater;
      }
    });

    handleModelSelectedEvent(ctx, modelSelectedData(PIPELINE));

    // The updater must return the SAME array reference (no clone) when no
    // assistant message needs stamping — this is the explicit short-circuit
    // in the retroactive logic.  That way React skips the re-render.
    expect(applied).toBe(initial);
  });

  it("stamps every assistant message that is missing modelId (null or empty string)", () => {
    const { ctx } = makeCtx();
    const setMessagesSpy = vi.spyOn(ctx, "setMessages");

    const initial: Message[] = [
      {
        role: "assistant",
        content: "first",
        modelId: null,
        timestamp: "2026-01-01T00:00:00.000Z",
      },
      {
        role: "user",
        content: "hello",
        timestamp: "2026-01-01T00:00:01.000Z",
      },
      {
        role: "assistant",
        content: "second",
        modelId: "",
        timestamp: "2026-01-01T00:00:02.000Z",
      },
      {
        role: "assistant",
        content: "third",
        modelId: "claude-3",
        timestamp: "2026-01-01T00:00:03.000Z",
      },
    ];

    let applied: Message[] = initial;
    setMessagesSpy.mockImplementation((updater) => {
      if (typeof updater === "function") {
        applied = updater(initial);
      } else {
        applied = updater;
      }
    });

    handleModelSelectedEvent(ctx, modelSelectedData(PIPELINE));

    const first = applied[0];
    const second = applied[2];
    const third = applied[3];
    if (first?.role !== "assistant") throw new Error("expected assistant at 0");
    if (second?.role !== "assistant") throw new Error("expected assistant at 2");
    if (third?.role !== "assistant") throw new Error("expected assistant at 3");

    expect(first.modelId).toBe("gpt-4");
    expect(second.modelId).toBe("gpt-4");
    // pre-existing non-empty modelId stays untouched
    expect(third.modelId).toBe("claude-3");
  });

  it("sets streamState.pipeline to the incoming event pipeline", () => {
    const { ctx } = makeCtx();
    expect(ctx.streamState.pipeline).toBeNull();

    handleModelSelectedEvent(ctx, modelSelectedData(PIPELINE));

    expect(ctx.streamState.pipeline).toBe(PIPELINE);
    expect(ctx.streamState.pipeline?.planning.modelId).toBe("gpt-4");
    expect(ctx.streamState.currentModelId).toBe("gpt-4");
    expect(ctx.setSelectedModelId).toHaveBeenCalledWith("gpt-4");
  });
});
