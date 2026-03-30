import { describe, expect, it } from "vitest";
import type { AssistantMessage, Message, ToolCall, SubKaniActivity, UserMessage } from "@pathfinder/shared";
import { attachThinkingToLastAssistant } from "./attachThinkingToLastAssistant";

function assertAssistant(msg: Message): asserts msg is AssistantMessage {
  if (msg.role !== "assistant") throw new Error(`Expected assistant, got ${msg.role}`);
}

function makeUserMessage(overrides?: Partial<Omit<UserMessage, "role">>): UserMessage {
  return {
    role: "user",
    content: overrides?.content ?? "",
    timestamp: overrides?.timestamp ?? new Date().toISOString(),
    ...overrides,
  };
}

function makeAssistantMessage(overrides?: Partial<Omit<AssistantMessage, "role">>): AssistantMessage {
  return {
    role: "assistant",
    content: overrides?.content ?? "",
    timestamp: overrides?.timestamp ?? new Date().toISOString(),
    ...overrides,
  };
}

function makeToolCall(overrides?: Partial<ToolCall>): ToolCall {
  return {
    id: overrides?.id ?? "tc-1",
    name: overrides?.name ?? "some_tool",
    arguments: overrides?.arguments ?? {},
    result: overrides?.result ?? null,
  };
}

function makeActivity(
  calls?: Record<string, ToolCall[]>,
  status?: Record<string, string>,
): SubKaniActivity {
  return {
    calls: calls ?? { sub1: [makeToolCall({ id: "sub-tc-1" })] },
    status: status ?? { sub1: "done" },
  };
}

describe("attachThinkingToLastAssistant", () => {
  // ─── Early returns ─────────────────────────────────────────────────

  it("returns the same reference when calls is empty and activity is undefined", () => {
    const msgs = [makeUserMessage()];
    const result = attachThinkingToLastAssistant(msgs, []);
    expect(result).toBe(msgs);
  });

  it("returns the same reference when there are no assistant messages", () => {
    const msgs: Message[] = [
      makeUserMessage({ content: "hello" }),
      makeUserMessage({ content: "another user msg" }),
    ];
    const calls = [makeToolCall()];
    const result = attachThinkingToLastAssistant(msgs, calls);
    expect(result).toBe(msgs);
  });

  it("returns the same reference for an empty messages array", () => {
    const msgs: Message[] = [];
    const result = attachThinkingToLastAssistant(msgs, [makeToolCall()]);
    expect(result).toBe(msgs);
  });

  // ─── Attaching tool calls ──────────────────────────────────────────

  it("attaches tool calls to the last assistant message", () => {
    const msgs: Message[] = [
      makeUserMessage({ content: "q" }),
      makeAssistantMessage({ content: "a" }),
    ];
    const calls = [makeToolCall({ id: "tc-1", name: "do_thing" })];
    const result = attachThinkingToLastAssistant(msgs, calls);
    expect(result).not.toBe(msgs);
    expect(result).toHaveLength(2);
    const resultMsg = result[1]!;
    assertAssistant(resultMsg);
    expect(resultMsg.toolCalls).toEqual(calls);
    // Original should be unmodified
    assertAssistant(msgs[1]!);
    expect(msgs[1]!.toolCalls).toBeUndefined();
  });

  it("attaches activity to the last assistant message", () => {
    const msgs: Message[] = [makeAssistantMessage({ content: "a" })];
    const activity = makeActivity();
    const result = attachThinkingToLastAssistant(msgs, [], activity);
    expect(result).not.toBe(msgs);
    assertAssistant(result[0]!);
    expect(result[0]!.subKaniActivity).toEqual(activity);
  });

  it("attaches both tool calls and activity in one call", () => {
    const msgs: Message[] = [makeAssistantMessage({ content: "a" })];
    const calls = [makeToolCall()];
    const activity = makeActivity();
    const result = attachThinkingToLastAssistant(msgs, calls, activity);
    assertAssistant(result[0]!);
    expect(result[0]!.toolCalls).toEqual(calls);
    expect(result[0]!.subKaniActivity).toEqual(activity);
  });

  // ─── Skipping already-populated messages ───────────────────────────

  it("returns the same reference when the assistant already has both toolCalls and subKaniActivity", () => {
    const existing = makeAssistantMessage({
      content: "done",
      toolCalls: [makeToolCall({ id: "existing" })],
      subKaniActivity: makeActivity(),
    });
    const msgs: Message[] = [existing];
    const result = attachThinkingToLastAssistant(
      msgs,
      [makeToolCall({ id: "new" })],
      makeActivity({ sub2: [] }, { sub2: "running" }),
    );
    expect(result).toBe(msgs);
  });

  it("does not overwrite existing toolCalls when calls are provided", () => {
    const existingCalls = [makeToolCall({ id: "existing-tc" })];
    const msgs: Message[] = [
      makeAssistantMessage({
        content: "a",
        toolCalls: existingCalls,
      }),
    ];
    const activity = makeActivity();
    const result = attachThinkingToLastAssistant(
      msgs,
      [makeToolCall({ id: "new-tc" })],
      activity,
    );
    // toolCalls already present, so keep them; activity was empty, so attach
    assertAssistant(result[0]!);
    expect(result[0]!.toolCalls).toEqual(existingCalls);
    expect(result[0]!.subKaniActivity).toEqual(activity);
  });

  it("does not overwrite existing subKaniActivity when activity is provided", () => {
    const existingActivity = makeActivity(
      { old: [makeToolCall({ id: "old-sub" })] },
      { old: "completed" },
    );
    const msgs: Message[] = [
      makeAssistantMessage({
        content: "a",
        subKaniActivity: existingActivity,
      }),
    ];
    const calls = [makeToolCall({ id: "new-tc" })];
    const result = attachThinkingToLastAssistant(
      msgs,
      calls,
      makeActivity({ new_sub: [] }, { new_sub: "running" }),
    );
    // activity already present, keep it; toolCalls were empty, so attach
    assertAssistant(result[0]!);
    expect(result[0]!.subKaniActivity).toEqual(existingActivity);
    expect(result[0]!.toolCalls).toEqual(calls);
  });

  // ─── Targeting the *last* assistant message ────────────────────────

  it("attaches to the last assistant message, not the first", () => {
    const msgs: Message[] = [
      makeAssistantMessage({ content: "first" }),
      makeUserMessage({ content: "q" }),
      makeAssistantMessage({ content: "second" }),
    ];
    const calls = [makeToolCall()];
    const result = attachThinkingToLastAssistant(msgs, calls);
    assertAssistant(result[0]!);
    expect(result[0]!.toolCalls).toBeUndefined();
    assertAssistant(result[2]!);
    expect(result[2]!.toolCalls).toEqual(calls);
  });

  it("skips user messages when scanning backwards", () => {
    const msgs: Message[] = [
      makeAssistantMessage({ content: "a" }),
      makeUserMessage({ content: "u1" }),
      makeUserMessage({ content: "u2" }),
    ];
    const calls = [makeToolCall()];
    const result = attachThinkingToLastAssistant(msgs, calls);
    // Should find the assistant at index 0
    assertAssistant(result[0]!);
    expect(result[0]!.toolCalls).toEqual(calls);
  });

  // ─── Edge: empty calls array with activity provided ────────────────

  it("does not attach empty calls array, only attaches activity", () => {
    const msgs: Message[] = [makeAssistantMessage({ content: "a" })];
    const activity = makeActivity();
    const result = attachThinkingToLastAssistant(msgs, [], activity);
    // calls.length === 0, so toolCalls left as undefined
    assertAssistant(result[0]!);
    expect(result[0]!.toolCalls).toBeUndefined();
    expect(result[0]!.subKaniActivity).toEqual(activity);
  });

  // ─── Immutability ─────────────────────────────────────────────────

  it("returns a new array and new message object (shallow copy)", () => {
    const msgs: Message[] = [makeAssistantMessage({ content: "a" })];
    const calls = [makeToolCall()];
    const result = attachThinkingToLastAssistant(msgs, calls);
    expect(result).not.toBe(msgs);
    expect(result[0]).not.toBe(msgs[0]);
    // Content should be preserved
    expect(result[0]!.content).toBe("a");
    expect(result[0]!.role).toBe("assistant");
  });

  // ─── SubKaniActivity with empty calls/status ──────────────────────

  it("treats subKaniActivity with empty calls as not-yet-populated", () => {
    const msgs: Message[] = [
      makeAssistantMessage({
        content: "a",
        subKaniActivity: { calls: {}, status: {} },
      }),
    ];
    const activity = makeActivity();
    const result = attachThinkingToLastAssistant(msgs, [], activity);
    // Empty calls means hasActivity is false, so new activity should be attached
    assertAssistant(result[0]!);
    expect(result[0]!.subKaniActivity).toEqual(activity);
  });

  it("preserves other message fields when attaching", () => {
    const msgs: Message[] = [
      makeAssistantMessage({
        content: "a",
        citations: [
          {
            id: "c1",
            source: "pubmed",
            title: "Test",
          },
        ],
        reasoning: "I thought about it",
      }),
    ];
    const calls = [makeToolCall()];
    const result = attachThinkingToLastAssistant(msgs, calls);
    assertAssistant(result[0]!);
    assertAssistant(msgs[0]!);
    expect(result[0]!.citations).toEqual(msgs[0]!.citations);
    expect(result[0]!.reasoning).toBe("I thought about it");
    expect(result[0]!.toolCalls).toEqual(calls);
  });
});
