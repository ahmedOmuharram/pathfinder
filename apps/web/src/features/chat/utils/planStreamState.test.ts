import { describe, expect, it } from "vitest";
import type { Citation, Message, PlanningArtifact, ToolCall } from "@pathfinder/shared";
import {
  applyAssistantDelta,
  finalizeAssistantMessage,
  upsertSessionArtifact,
} from "@/features/chat/utils/planStreamState";

describe("planStreamState", () => {
  it("applyAssistantDelta starts a new streaming assistant message and appends deltas", () => {
    const nowIso = () => "2026-01-01T00:00:00.000Z";
    const base: Message[] = [{ role: "user", content: "hi", timestamp: nowIso() }];
    const started = applyAssistantDelta({
      messages: base,
      streaming: { index: null, messageId: null },
      event: { messageId: "m1", delta: "Hello" },
      nowIso,
    });
    expect(started.streaming).toEqual({ index: 1, messageId: "m1" });
    expect(started.messages[1]).toMatchObject({ role: "assistant", content: "Hello" });

    const appended = applyAssistantDelta({
      messages: started.messages,
      streaming: started.streaming,
      event: { messageId: "m1", delta: " world" },
      nowIso,
    });
    expect(appended.messages[1]?.content).toBe("Hello world");
  });

  it("finalizeAssistantMessage attaches buffers to streaming message and clears streaming state", () => {
    const nowIso = () => "2026-01-01T00:00:00.000Z";
    const messages: Message[] = [
      { role: "user", content: "u", timestamp: nowIso() },
      { role: "assistant", content: "partial", timestamp: nowIso() },
    ];
    const toolCalls: ToolCall[] = [
      { id: "t1", name: "tool", arguments: { a: 1 } } as any,
    ];
    const citations: Citation[] = [{ sourceId: "s", quote: "q" } as any];
    const artifacts: PlanningArtifact[] = [{ id: "a1", title: "A" } as any];

    const result = finalizeAssistantMessage({
      messages,
      streaming: { index: 1, messageId: "m1" },
      event: { messageId: "m1", content: "final" },
      toolCallsBuffer: toolCalls,
      citationsBuffer: citations,
      artifactsBuffer: artifacts,
      nowIso,
    });
    expect(result.streaming).toEqual({ index: null, messageId: null });
    expect(result.messages[1]).toMatchObject({
      role: "assistant",
      content: "final",
      toolCalls,
      citations,
      planningArtifacts: artifacts,
    });
  });

  it("upsertSessionArtifact replaces by id when present, otherwise appends", () => {
    const a1 = { id: "x", title: "old" } as any as PlanningArtifact;
    const a2 = { id: "x", title: "new" } as any as PlanningArtifact;
    const b1 = { id: "y", title: "y" } as any as PlanningArtifact;

    expect(upsertSessionArtifact([a1], a2)).toEqual([a2]);
    expect(upsertSessionArtifact([a1], b1)).toEqual([a1, b1]);
  });
});
