import { describe, expect, it, vi } from "vitest";
import { handleChatEvent } from "./handleChatEvent";
import type { ChatSSEEvent } from "@/features/chat/sse_events";
import { PLAN_ARTIFACT_EVENTS } from "./__fixtures__/realisticEvents";
import { makeCtx } from "./handleChatEvent.testUtils";

describe("handleChatEvent — realistic plan mode", () => {
  it("processes planning events and fires callbacks", () => {
    const onPlanSessionId = vi.fn();
    const onPlanningArtifactUpdate = vi.fn();
    const onExecutorBuildRequest = vi.fn();

    const { ctx, state } = makeCtx({
      onPlanSessionId,
      onPlanningArtifactUpdate,
      onExecutorBuildRequest,
    });

    for (const event of PLAN_ARTIFACT_EVENTS) {
      handleChatEvent(ctx, event as ChatSSEEvent);
    }

    // ── Artifact should be buffered then attached ──
    expect(state.messages).toHaveLength(1);
    const msg = state.messages[0]!;
    expect(msg.planningArtifacts).toBeDefined();
    expect(msg.planningArtifacts!.length).toBeGreaterThan(0);
    expect(msg.planningArtifacts![0]?.title).toBe("Vaccine target search plan");

    // ── Callbacks fired ──
    expect(onPlanningArtifactUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ id: "artifact-001" }),
    );
    expect(onExecutorBuildRequest).toHaveBeenCalled();

    // Refs cleaned up
    expect(ctx.streamState.streamingAssistantIndex).toBeNull();
  });
});
