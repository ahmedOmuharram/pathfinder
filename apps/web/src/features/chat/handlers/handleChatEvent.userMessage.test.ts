/**
 * Tests for user_message event handling during operation recovery.
 *
 * When a user refreshes the page during streaming, the operation recovery
 * hook re-subscribes to the SSE stream and replays catch-up events from
 * Redis.  These events include `user_message` which must be processed
 * so `mergeMessages` sees a complete conversation (user + assistant).
 */

import { describe, expect, it, vi } from "vitest";
import type { SetStateAction } from "react";
import type { Message } from "@pathfinder/shared";
import { handleUserMessageEvent } from "./handleChatEvent.messageEvents";
import { handleChatEvent } from "./handleChatEvent";
import type { ChatEventContext } from "./handleChatEvent.types";

function makeMinimalCtx(overrides: Partial<ChatEventContext> = {}): ChatEventContext {
  return {
    siteId: "test",
    strategyIdAtStart: "s1",
    toolCallsBuffer: [],
    citationsBuffer: [],
    planningArtifactsBuffer: [],
    subKaniCallsBuffer: {},
    subKaniStatusBuffer: {},
    subKaniModelsBuffer: {},
    subKaniTokenUsageBuffer: {},
    thinking: {
      reset: vi.fn(),
      updateReasoning: vi.fn(),
      finalizeToolCalls: vi.fn(),
      appendToolCall: vi.fn(),
      finalizeToolCall: vi.fn(),
    } as unknown as ChatEventContext["thinking"],
    setStrategyId: vi.fn(),
    addStrategy: vi.fn(),
    addExecutedStrategy: vi.fn(),
    setWdkInfo: vi.fn(),
    setStrategy: vi.fn(),
    setStrategyMeta: vi.fn(),
    clearStrategy: vi.fn(),
    addStep: vi.fn(),
    loadGraph: vi.fn(),
    session: {
      latestStrategy: null,
      snapshotApplied: false,
      consumeUndoSnapshot: vi.fn(() => null),
    } as unknown as ChatEventContext["session"],
    currentStrategy: null,
    setMessages: vi.fn(),
    setUndoSnapshots: vi.fn(),
    parseToolArguments: vi.fn(() => ({})),
    parseToolResult: vi.fn(() => null),
    applyGraphSnapshot: vi.fn(),
    getStrategy: vi.fn(async () => null) as unknown as ChatEventContext["getStrategy"],
    streamState: {
      streamingAssistantIndex: null,
      streamingAssistantMessageId: null,
      turnAssistantIndex: null,
      reasoning: null,
      optimizationProgress: null,
    },
    setOptimizationProgress: vi.fn(),
    ...overrides,
  };
}

describe("handleUserMessageEvent", () => {
  it("appends a user message to empty messages array", () => {
    const messages: Message[] = [];
    const setMessages = vi.fn((value: SetStateAction<Message[]>) => {
      const next = typeof value === "function" ? value(messages) : value;
      messages.push(...next.slice(messages.length));
    });
    const ctx = makeMinimalCtx({ setMessages });

    handleUserMessageEvent(ctx, { content: "hello", messageId: "m1" });

    const updater = setMessages.mock.calls[0][0] as (prev: Message[]) => Message[];
    const result = updater([]);
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({ role: "user", content: "hello" });
  });

  it("deduplicates when the same user message already exists", () => {
    const existing: Message[] = [
      { role: "user", content: "hello", timestamp: "2026-01-01T00:00:00Z" },
    ];
    const setMessages = vi.fn();
    const ctx = makeMinimalCtx({ setMessages });

    handleUserMessageEvent(ctx, { content: "hello", messageId: "m1" });

    const updater = setMessages.mock.calls[0][0] as (prev: Message[]) => Message[];
    const result = updater(existing);
    // Should return existing array unchanged (dedup)
    expect(result).toBe(existing);
    expect(result).toHaveLength(1);
  });

  it("appends when content differs from existing user message", () => {
    const existing: Message[] = [
      { role: "user", content: "first question", timestamp: "2026-01-01T00:00:00Z" },
      { role: "assistant", content: "answer", timestamp: "2026-01-01T00:00:01Z" },
    ];
    const setMessages = vi.fn();
    const ctx = makeMinimalCtx({ setMessages });

    handleUserMessageEvent(ctx, { content: "second question", messageId: "m2" });

    const updater = setMessages.mock.calls[0][0] as (prev: Message[]) => Message[];
    const result = updater(existing);
    expect(result).toHaveLength(3);
    expect(result[2]).toMatchObject({ role: "user", content: "second question" });
  });

  it("ignores events with empty content", () => {
    const setMessages = vi.fn();
    const ctx = makeMinimalCtx({ setMessages });

    handleUserMessageEvent(ctx, { content: "", messageId: "m1" });
    expect(setMessages).not.toHaveBeenCalled();

    handleUserMessageEvent(ctx, { messageId: "m2" });
    expect(setMessages).not.toHaveBeenCalled();
  });
});

describe("handleChatEvent dispatches user_message", () => {
  it("routes user_message events to handleUserMessageEvent", () => {
    const setMessages = vi.fn();
    const ctx = makeMinimalCtx({ setMessages });

    handleChatEvent(ctx, {
      type: "user_message",
      data: { content: "test message", messageId: "m1" },
    });

    expect(setMessages).toHaveBeenCalledTimes(1);
  });
});

describe("recovery catch-up produces complete conversation", () => {
  it("user_message + assistant_delta + assistant_message produces [user, assistant]", () => {
    let messages: Message[] = [];
    const setMessages = vi.fn((updater: unknown) => {
      if (typeof updater === "function") {
        messages = (updater as (prev: Message[]) => Message[])(messages);
      }
    });
    const streamState = {
      streamingAssistantIndex: null as number | null,
      streamingAssistantMessageId: null as string | null,
      turnAssistantIndex: null as number | null,
      reasoning: null,
      optimizationProgress: null,
    };
    const ctx = makeMinimalCtx({ setMessages, streamState });

    // Simulate recovery catch-up events in order:
    handleChatEvent(ctx, {
      type: "user_message",
      data: { content: "analyze genes", messageId: "u1" },
    });

    expect(messages).toHaveLength(1);
    expect(messages[0].role).toBe("user");

    handleChatEvent(ctx, {
      type: "message_start",
      data: {},
    });

    handleChatEvent(ctx, {
      type: "assistant_delta",
      data: { delta: "Here are ", messageId: "a1" },
    });

    expect(messages).toHaveLength(2);
    expect(messages[1].role).toBe("assistant");
    expect(messages[1].content).toBe("Here are ");

    handleChatEvent(ctx, {
      type: "assistant_delta",
      data: { delta: "the results", messageId: "a1" },
    });

    expect(messages[1].content).toBe("Here are the results");

    handleChatEvent(ctx, {
      type: "assistant_message",
      data: { content: "Here are the results", messageId: "a1" },
    });

    // Final state: [user, assistant] — complete conversation
    expect(messages).toHaveLength(2);
    expect(messages[0]).toMatchObject({ role: "user", content: "analyze genes" });
    expect(messages[1]).toMatchObject({
      role: "assistant",
      content: "Here are the results",
    });
  });
});
