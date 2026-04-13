// @vitest-environment jsdom
import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatSessionProvider, useChatSessionContext } from "./useChatContext";

function makeMockChatSession() {
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

describe("useChatSessionContext", () => {
  it("returns the session value provided by the ChatSessionProvider", () => {
    const session = makeMockChatSession();
    const { result } = renderHook(() => useChatSessionContext(), {
      wrapper: ({ children }) => (
        <ChatSessionProvider session={session}>{children}</ChatSessionProvider>
      ),
    });
    expect(result.current).toBe(session);
  });

  it("throws when used without a ChatSessionProvider", () => {
    // React logs the thrown error on stderr — silence it for the test.
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => renderHook(() => useChatSessionContext())).toThrow(
      /ChatSessionProvider/,
    );
    consoleError.mockRestore();
  });
});
