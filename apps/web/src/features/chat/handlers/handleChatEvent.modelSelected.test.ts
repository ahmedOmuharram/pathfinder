import { describe, it, expect } from "vitest";
import { makeCtx } from "./handleChatEvent.testUtils";
import {
  handleAssistantDeltaEvent,
  handleModelSelectedEvent,
} from "./handleChatEvent.messageEvents";
import type { ModelSelectedData, PipelineConfig } from "@pathfinder/shared";

const PIPELINE: PipelineConfig = {
  scoping: { modelId: "claude-sonnet-4-20250514", reasoningEffort: "low" },
  discovery: { modelId: "claude-sonnet-4-20250514", reasoningEffort: "medium" },
  planning: { modelId: "claude-opus-4-20250514", reasoningEffort: "high" },
  execution: { modelId: "claude-sonnet-4-20250514", reasoningEffort: "medium" },
  verification: { modelId: "claude-sonnet-4-20250514", reasoningEffort: "low" },
};

function modelSelectedData(pipeline: PipelineConfig): ModelSelectedData {
  return { pipeline };
}

describe("handleModelSelectedEvent", () => {
  it("sets currentModelId from the planning phase", () => {
    const { ctx } = makeCtx();
    handleModelSelectedEvent(ctx, modelSelectedData(PIPELINE));
    expect(ctx.streamState.currentModelId).toBe("claude-opus-4-20250514");
  });

  it("stores the full pipeline on stream state", () => {
    const { ctx } = makeCtx();
    handleModelSelectedEvent(ctx, modelSelectedData(PIPELINE));
    expect(ctx.streamState.pipeline).toEqual(PIPELINE);
  });

  it("calls setSelectedModelId callback", () => {
    const { ctx } = makeCtx();
    handleModelSelectedEvent(ctx, modelSelectedData(PIPELINE));
    expect(ctx.setSelectedModelId).toHaveBeenCalledWith("claude-opus-4-20250514");
  });

  it("retroactively stamps modelId on existing assistant messages missing it", () => {
    const { ctx, state } = makeCtx();

    // Simulate assistant_delta arriving BEFORE model_selected
    handleAssistantDeltaEvent(ctx, {
      delta: "Hello",
      messageId: "msg-1",
    });
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0]?.role).toBe("assistant");
    // modelId is missing because currentModelId was not yet set
    expect((state.messages[0] as { modelId?: string }).modelId).toBeUndefined();

    // Now model_selected arrives — should retroactively stamp the message
    handleModelSelectedEvent(ctx, modelSelectedData(PIPELINE));

    expect((state.messages[0] as { modelId?: string }).modelId).toBe(
      "claude-opus-4-20250514",
    );
  });

  it("does not overwrite modelId on messages that already have one", () => {
    const { ctx, state } = makeCtx();

    // Set a different model first
    ctx.streamState.currentModelId = "old-model-id";
    handleAssistantDeltaEvent(ctx, {
      delta: "First message",
      messageId: "msg-1",
    });
    expect((state.messages[0] as { modelId?: string }).modelId).toBe("old-model-id");

    // model_selected arrives with a different model
    handleModelSelectedEvent(ctx, modelSelectedData(PIPELINE));

    // Should NOT overwrite the existing modelId
    expect((state.messages[0] as { modelId?: string }).modelId).toBe("old-model-id");
  });

  it("stamps multiple assistant messages that are all missing modelId", () => {
    const { ctx, state } = makeCtx();

    // Two assistant messages created before model_selected
    handleAssistantDeltaEvent(ctx, { delta: "First", messageId: "msg-1" });
    // Reset streaming index so a new message is created
    ctx.streamState.streamingAssistantIndex = null;
    ctx.streamState.streamingAssistantMessageId = null;
    handleAssistantDeltaEvent(ctx, { delta: "Second", messageId: "msg-2" });

    expect(state.messages).toHaveLength(2);
    expect((state.messages[0] as { modelId?: string }).modelId).toBeUndefined();
    expect((state.messages[1] as { modelId?: string }).modelId).toBeUndefined();

    handleModelSelectedEvent(ctx, modelSelectedData(PIPELINE));

    expect((state.messages[0] as { modelId?: string }).modelId).toBe(
      "claude-opus-4-20250514",
    );
    expect((state.messages[1] as { modelId?: string }).modelId).toBe(
      "claude-opus-4-20250514",
    );
  });
});

describe("assistant_delta after model_selected (normal flow)", () => {
  it("creates message with modelId when currentModelId is already set", () => {
    const { ctx, state } = makeCtx();

    // model_selected arrives first (normal flow)
    handleModelSelectedEvent(ctx, modelSelectedData(PIPELINE));

    // Then assistant_delta
    handleAssistantDeltaEvent(ctx, {
      delta: "Hello",
      messageId: "msg-1",
    });

    expect(state.messages).toHaveLength(1);
    expect((state.messages[0] as { modelId?: string }).modelId).toBe(
      "claude-opus-4-20250514",
    );
  });
});
