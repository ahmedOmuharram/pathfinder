// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PathfinderUIMessage } from "@pathfinder/shared";

import { ChatSessionProvider } from "./approval/useChatContext";
import { MessageBubble } from "./MessageBubble";

vi.mock("@/lib/api/feedback", () => ({
  submitFeedback: vi.fn().mockResolvedValue(undefined),
}));

/**
 * Default metadata shape for a completed assistant message used by the
 * strict-mode tests. Must include every field required by
 * `CompletedAssistantMetadata`; swap individual fields per test as needed.
 */
const COMPLETE_META = {
  phase: "completed" as const,
  model: "anthropic/claude-sonnet-4-6",
  traceId: "trace-xyz",
  createdAt: "2026-04-13T08:00:00Z",
};

function makeMockSession() {
  return {
    addToolApprovalResponse: vi.fn(),
    addToolOutput: vi.fn(),
    sendMessage: vi.fn(),
    stop: vi.fn(),
    regenerate: vi.fn(),
    setMessages: vi.fn(),
    clearError: vi.fn(),
    resumeStream: vi.fn(),
    messages: [],
    status: "ready" as const,
    error: undefined,
    id: "test",
  } as unknown as Parameters<typeof ChatSessionProvider>[0]["session"];
}

function msg(partial: Partial<PathfinderUIMessage>): PathfinderUIMessage {
  return {
    id: "m1",
    role: "user",
    parts: [],
    ...partial,
  } as PathfinderUIMessage;
}

function renderWithSession(
  children: React.ReactNode,
  session: Parameters<typeof ChatSessionProvider>[0]["session"] = makeMockSession(),
) {
  return render(
    <ChatSessionProvider session={session}>{children}</ChatSessionProvider>,
  );
}

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("MessageBubble", () => {
  it("renders children with a role-based data attribute", () => {
    renderWithSession(
      <MessageBubble
        message={msg({ role: "user" })}
        isLatest={false}
        isComplete={true}
      >
        <div>contents</div>
      </MessageBubble>,
    );
    const bubble = screen.getByTestId("message-bubble");
    expect(bubble.getAttribute("data-role")).toBe("user");
    expect(screen.getByText("contents")).toBeInTheDocument();
  });

  it("renders completed assistant header with all fields present", () => {
    renderWithSession(
      <MessageBubble
        message={msg({
          role: "assistant",
          metadata: { ...COMPLETE_META, phase: "discovery" },
        })}
        isLatest
        isComplete
      >
        <div>ok</div>
      </MessageBubble>,
    );
    expect(screen.getByTestId("message-phase").textContent).toBe("discovery");
    expect(screen.getByTestId("message-model").textContent).toBe(
      "claude-sonnet-4-6",
    );
    expect(screen.getByTestId("message-time")).toBeInTheDocument();
  });

  it("throws when a completed assistant message is missing required metadata", () => {
    const session = makeMockSession();
    const prev = console.error;
    console.error = () => {};
    expect(() =>
      render(
        <ChatSessionProvider session={session}>
          <MessageBubble
            message={msg({ role: "assistant", id: "broken" })}
            isLatest={false}
            isComplete
          >
            <div />
          </MessageBubble>
        </ChatSessionProvider>,
      ),
    ).toThrow(/broken/);
    console.error = prev;
  });

  it("renders partial metadata on a streaming assistant message without throwing", () => {
    renderWithSession(
      <MessageBubble
        message={msg({
          role: "assistant",
          metadata: { phase: "planning" },
        })}
        isLatest
        isComplete={false}
      >
        <div>streaming…</div>
      </MessageBubble>,
    );
    expect(screen.getByTestId("message-phase").textContent).toBe("planning");
  });

  it("renders an avatar for assistant and user (not system)", () => {
    renderWithSession(
      <MessageBubble
        message={msg({ role: "assistant", metadata: COMPLETE_META })}
        isLatest
        isComplete
      >
        <div />
      </MessageBubble>,
    );
    expect(screen.getByTestId("message-avatar").getAttribute("data-role")).toBe(
      "assistant",
    );
  });

  it("shows a regenerate button only on the latest assistant bubble", () => {
    const session = makeMockSession();
    const { rerender } = renderWithSession(
      <MessageBubble
        message={msg({ role: "assistant", metadata: COMPLETE_META })}
        isLatest
        isComplete
      >
        <div />
      </MessageBubble>,
      session,
    );
    fireEvent.click(screen.getByTestId("message-regenerate"));
    expect(session.regenerate).toHaveBeenCalledTimes(1);

    rerender(
      <ChatSessionProvider session={session}>
        <MessageBubble
          message={msg({ role: "assistant", metadata: COMPLETE_META })}
          isLatest={false}
          isComplete
        >
          <div />
        </MessageBubble>
      </ChatSessionProvider>,
    );
    expect(screen.queryByTestId("message-regenerate")).not.toBeInTheDocument();
  });

  it("calls submitFeedback with value=1 when thumbs up is clicked", async () => {
    const { submitFeedback } = await import("@/lib/api/feedback");
    renderWithSession(
      <MessageBubble
        message={msg({
          role: "assistant",
          id: "m-abc",
          metadata: { ...COMPLETE_META, traceId: "trace-xyz" },
        })}
        isLatest={false}
        isComplete
      >
        <div />
      </MessageBubble>,
    );
    fireEvent.click(screen.getByTestId("message-thumbs-up"));
    expect(submitFeedback).toHaveBeenCalledWith({
      traceId: "trace-xyz",
      streamId: "m-abc",
      value: 1,
    });
  });

  it("does not render avatar or footer for system messages", () => {
    renderWithSession(
      <MessageBubble
        message={msg({ role: "system" })}
        isLatest={false}
        isComplete
      >
        <div>system text</div>
      </MessageBubble>,
    );
    expect(screen.queryByTestId("message-avatar")).not.toBeInTheDocument();
    expect(screen.queryByTestId("message-footer")).not.toBeInTheDocument();
  });

  describe("token usage Context", () => {
    it("renders the Context indicator when both tokensUsed and tokensBudget are present", () => {
      renderWithSession(
        <MessageBubble
          message={msg({
            role: "assistant",
            metadata: { ...COMPLETE_META, tokensUsed: 5_000, tokensBudget: 100_000 },
          })}
          isLatest
          isComplete
        >
          <div />
        </MessageBubble>,
      );
      expect(screen.getByTestId("message-context")).toBeInTheDocument();
      // 5000/100000 = 5%
      expect(screen.getByTestId("message-context")).toHaveTextContent("5%");
    });

    it("hides the Context indicator when tokensUsed is missing", () => {
      renderWithSession(
        <MessageBubble
          message={msg({
            role: "assistant",
            metadata: { ...COMPLETE_META, tokensBudget: 100_000 },
          })}
          isLatest
          isComplete
        >
          <div />
        </MessageBubble>,
      );
      expect(screen.queryByTestId("message-context")).not.toBeInTheDocument();
    });

    it("hides the Context indicator when tokensBudget is missing", () => {
      renderWithSession(
        <MessageBubble
          message={msg({
            role: "assistant",
            metadata: { ...COMPLETE_META, tokensUsed: 1_000 },
          })}
          isLatest
          isComplete
        >
          <div />
        </MessageBubble>,
      );
      expect(screen.queryByTestId("message-context")).not.toBeInTheDocument();
    });

    it("hides the Context indicator when tokensBudget is zero (avoids divide-by-zero)", () => {
      renderWithSession(
        <MessageBubble
          message={msg({
            role: "assistant",
            metadata: { ...COMPLETE_META, tokensUsed: 1_000, tokensBudget: 0 },
          })}
          isLatest
          isComplete
        >
          <div />
        </MessageBubble>,
      );
      expect(screen.queryByTestId("message-context")).not.toBeInTheDocument();
    });
  });
});
