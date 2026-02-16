// @vitest-environment jsdom
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { Message, OptimizationProgressData } from "@pathfinder/shared";
import { ChatMessageList } from "@/features/chat/components/ChatMessageList";

vi.mock("@/features/chat/components/ChatEmptyState", () => ({
  ChatEmptyState: () => null,
}));

vi.mock("@/features/chat/components/NodeCard", () => ({
  NodeCard: () => null,
}));

vi.mock("@/features/chat/components/ChatMarkdown", () => ({
  ChatMarkdown: ({ content }: { content: string }) => <span>{content}</span>,
}));

vi.mock("@/features/chat/components/ThinkingPanel", () => ({
  ThinkingPanel: () => <div data-testid="floating-thinking">Thinking</div>,
}));

vi.mock("@/features/chat/components/OptimizationProgressPanel", () => ({
  OptimizationProgressPanel: ({ data }: { data: OptimizationProgressData }) => (
    <div data-testid="floating-optimization">{data.status}</div>
  ),
}));

vi.mock("@/features/chat/components/AssistantMessageParts", () => ({
  AssistantMessageParts: ({
    index,
    message,
    optimizationProgress,
  }: {
    index: number;
    message: Message;
    optimizationProgress?: OptimizationProgressData | null;
  }) => (
    <div data-testid={`assistant-${index}`}>
      <span data-testid={`assistant-${index}-content`}>{message.content}</span>
      <span data-testid={`assistant-${index}-live-opt`}>
        {optimizationProgress ? "live" : "none"}
      </span>
      <span data-testid={`assistant-${index}-saved-opt`}>
        {message.optimizationProgress ? "saved" : "none"}
      </span>
    </div>
  ),
}));

function makeOpt(status: OptimizationProgressData["status"]): OptimizationProgressData {
  return {
    optimizationId: "opt-1",
    status,
    currentTrial: 1,
    totalTrials: 10,
    recentTrials: [],
  };
}

function makeAssistant(
  content: string,
  optimizationProgress?: OptimizationProgressData,
): Message {
  return {
    role: "assistant",
    content,
    optimizationProgress,
    timestamp: "2026-01-01T00:00:00.000Z",
  };
}

describe("ChatMessageList UI ownership", () => {
  afterEach(() => {
    cleanup();
  });

  const baseProps = {
    isCompact: false,
    siteId: "PlasmoDB",
    displayName: "PlasmoDB",
    signedIn: false,
    mode: "execute" as const,
    undoSnapshots: {},
    onSend: vi.fn(),
    onUndoSnapshot: vi.fn(),
    thinking: {
      activeToolCalls: [],
      lastToolCalls: [],
      subKaniCalls: {},
      subKaniStatus: {},
      reasoning: null,
    },
    messagesEndRef: { current: null },
  };

  it("does not attach live optimization to previous assistant when current turn has no assistant yet", () => {
    const messages: Message[] = [
      makeAssistant("previous assistant"),
      {
        role: "user",
        content: "new turn question",
        timestamp: "2026-01-01T00:00:01.000Z",
      },
    ];

    render(
      <ChatMessageList
        {...baseProps}
        isStreaming
        messages={messages}
        optimizationProgress={makeOpt("running")}
      />,
    );

    expect(screen.getByTestId("assistant-0-live-opt").textContent).toBe("none");
    expect(screen.getByTestId("floating-optimization")).toBeTruthy();
  });

  it("keeps saved optimization on previous assistant while not injecting live optimization into it", () => {
    const saved = makeOpt("completed");
    const messages: Message[] = [
      makeAssistant("previous assistant", saved),
      {
        role: "user",
        content: "new turn question",
        timestamp: "2026-01-01T00:00:01.000Z",
      },
    ];

    render(
      <ChatMessageList
        {...baseProps}
        isStreaming
        messages={messages}
        optimizationProgress={makeOpt("running")}
      />,
    );

    expect(screen.getByTestId("assistant-0-saved-opt").textContent).toBe("saved");
    expect(screen.getByTestId("assistant-0-live-opt").textContent).toBe("none");
  });

  it("renders saved optimization on message after streaming ends (isStreaming=false)", () => {
    const saved = makeOpt("completed");
    const messages: Message[] = [makeAssistant("response with optimization", saved)];

    render(
      <ChatMessageList
        {...baseProps}
        isStreaming={false}
        messages={messages}
        optimizationProgress={null}
      />,
    );

    expect(screen.getByTestId("assistant-0-saved-opt").textContent).toBe("saved");
    expect(screen.getByTestId("assistant-0-live-opt").textContent).toBe("none");
  });

  it("renders live optimization on last assistant when streaming is active", () => {
    const messages: Message[] = [makeAssistant("streaming response")];

    render(
      <ChatMessageList
        {...baseProps}
        isStreaming
        messages={messages}
        optimizationProgress={makeOpt("running")}
      />,
    );

    expect(screen.getByTestId("assistant-0-live-opt").textContent).toBe("live");
  });
});
