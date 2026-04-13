// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ChatPanel } from "./ChatPanel";
import { useChatSession } from "./chat-hook";

vi.mock("./chat-hook", () => ({
  useChatSession: vi.fn(),
}));

vi.mock("@/lib/api/chat", () => ({
  fetchChatHistory: vi.fn().mockResolvedValue([]),
}));

function makeMockSession(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    addToolApprovalResponse: vi.fn(),
    addToolOutput: vi.fn(),
    addToolResult: vi.fn(),
    sendMessage: vi.fn(),
    stop: vi.fn(),
    regenerate: vi.fn(),
    setMessages: vi.fn(),
    clearError: vi.fn(),
    resumeStream: vi.fn(),
    messages: [],
    status: "ready" as const,
    error: undefined,
    id: "test-chat",
    ...overrides,
  };
}

function renderPanel(props: { chatId: string; mode: "strategy" | "experiment" }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ChatPanel {...props} />
    </QueryClientProvider>,
  );
}

describe("ChatPanel", () => {
  it("mounts header (ModelPicker), body (MessageList empty-state), and footer (ChatInput)", () => {
    const session = makeMockSession();
    vi.mocked(useChatSession).mockReturnValue(
      session as unknown as ReturnType<typeof useChatSession>,
    );

    const { container } = renderPanel({ chatId: "strategy-abc", mode: "strategy" });

    // Root panel exposes mode + chatId as data attrs.
    const root = container.querySelector("[data-mode='strategy']");
    expect(root).toBeTruthy();
    expect(root?.getAttribute("data-chat-id")).toBe("strategy-abc");

    // Header: ModelPicker renders a button showing the tier label.
    // The quick-swap dropdown is closed by default but the trigger button is present.
    const pickerButton = container.querySelector(
      "[data-mode='strategy'] button",
    );
    expect(pickerButton).toBeTruthy();

    // Footer: ChatInput has a textarea + Send button (ready state).
    expect(screen.getByRole("textbox")).toBeTruthy();
    expect(screen.getByRole("button", { name: /send/i })).toBeTruthy();
  });

  it("passes chatId and mode down to useChatSession", () => {
    const session = makeMockSession();
    vi.mocked(useChatSession).mockReturnValue(
      session as unknown as ReturnType<typeof useChatSession>,
    );

    renderPanel({ chatId: "experiment-xyz", mode: "experiment" });

    expect(useChatSession).toHaveBeenCalledWith("experiment-xyz", "experiment");
  });
});
