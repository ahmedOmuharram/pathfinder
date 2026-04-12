// @vitest-environment jsdom
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type {
  AssistantMessage,
  Message,
  OptimizationProgressData,
  UserMessage,
} from "@pathfinder/shared";
import { ChatMessageList } from "@/features/chat/components/ChatMessageList";
import { useSessionStore } from "@/state/useSessionStore";

vi.mock("@/lib/query/hooks/useModelCatalogQuery", () => ({
  useModelCatalogQuery: () => ({ data: undefined }),
}));

vi.mock("@/lib/components/ProviderIcon", () => ({
  ProviderIcon: () => null,
}));

vi.mock("@/features/chat/components/ChatEmptyState", () => ({
  ChatEmptyState: () => null,
}));

vi.mock("@/features/chat/components/delegation/NodeCard", () => ({
  NodeCard: () => null,
}));

vi.mock("@/features/chat/components/message/ChatMarkdown", () => ({
  ChatMarkdown: ({ content }: { content: string }) => <span>{content}</span>,
}));

vi.mock("@/features/chat/components/thinking/ThinkingPanel", () => ({
  ThinkingPanel: () => <div data-testid="floating-thinking">Thinking</div>,
}));

vi.mock("@/features/chat/components/optimization/OptimizationProgressPanel", () => ({
  OptimizationProgressPanel: ({ data }: { data: OptimizationProgressData }) => (
    <div data-testid="floating-optimization">{data.status}</div>
  ),
}));

vi.mock("@/features/chat/components/message/AssistantMessageParts", () => ({
  AssistantMessageParts: ({
    index,
    message,
    isLive,
    optimizationProgress,
  }: {
    index: number;
    message: AssistantMessage;
    isLive: boolean;
    optimizationProgress?: OptimizationProgressData | null;
  }) => (
    <div data-testid={`assistant-${index}`}>
      <span data-testid={`assistant-${index}-content`}>{message.content}</span>
      <span data-testid={`assistant-${index}-is-live`}>
        {isLive ? "live" : "idle"}
      </span>
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
  messageId?: string,
): AssistantMessage {
  return {
    role: "assistant",
    content,
    ...(messageId != null ? { messageId } : {}),
    ...(optimizationProgress != null ? { optimizationProgress } : {}),
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
    mode: "execute" as const,
    undoSnapshots: {},
    onSend: vi.fn(),
    onUndoSnapshot: vi.fn(),
    thinking: {
      activeMessageId: null,
      activeToolCalls: [],
      lastToolCalls: [],
      reasoning: null,
      getThinkingForMessage: () => ({
        activeToolCalls: [],
        lastToolCalls: [],
        reasoning: null,
      }),
    },
    messagesEndRef: { current: null },
  };

  useSessionStore.setState({ strategyId: "strategy-123" });

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

  it("does not keep the previous phase assistant live after a new phase starts", () => {
    const messages: Message[] = [makeAssistant("execution summary", undefined, "exec-msg")];

    render(
      <ChatMessageList
        {...baseProps}
        isStreaming
        messages={messages}
        thinking={{
          ...baseProps.thinking,
          activeMessageId: "verify-msg",
          getThinkingForMessage: (messageId?: string | null) =>
            messageId === "verify-msg"
              ? {
                  activeToolCalls: [{ id: "tool-1", name: "verify", arguments: {} }],
                  lastToolCalls: [],
                  reasoning: "Verifying results",
                }
              : {
                  activeToolCalls: [],
                  lastToolCalls: [],
                  reasoning: null,
                },
        }}
      />,
    );

    expect(screen.getByTestId("assistant-0-is-live").textContent).toBe("idle");
    expect(screen.getByTestId("floating-thinking")).toBeTruthy();
  });

  it("offers regenerate for assistant turns with a preceding user message", () => {
    const handleRegenerate = vi.fn();
    const userMessage: UserMessage = {
      role: "user",
      content: "find transporters",
      mentions: [{ type: "strategy", id: "s1", displayName: "Strategy 1" }],
      timestamp: "2026-01-01T00:00:00.000Z",
    };
    const assistantMessage = makeAssistant("here is a plan");
    assistantMessage.traceId = "trace-123";
    const messages: Message[] = [userMessage, assistantMessage];

    render(
      <ChatMessageList
        {...baseProps}
        isStreaming={false}
        messages={messages}
        onRegenerate={handleRegenerate}
      />,
    );

    fireEvent.click(screen.getByLabelText("Regenerate response"));

    expect(handleRegenerate).toHaveBeenCalledWith(userMessage, assistantMessage);
  });
});
