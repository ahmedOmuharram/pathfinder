// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApprovalDialog } from "./ApprovalDialog";
import { ChatSessionProvider } from "./useChatContext";

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

describe("ApprovalDialog", () => {
  it("renders the tool name and Allow/Deny buttons for an approval-requested part", () => {
    const session = makeMockChatSession();
    render(
      <ChatSessionProvider session={session}>
        <ApprovalDialog
          part={{
            type: "tool-delete_strategy",
            toolCallId: "tc-approve-1",
            state: "approval-requested",
            input: { strategy_id: "s_x" },
            approval: { id: "approve-1" },
          }}
        />
      </ChatSessionProvider>,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeTruthy();
    expect(dialog.getAttribute("data-tool")).toBe("delete_strategy");
    expect(screen.getByRole("button", { name: /allow/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /deny/i })).toBeTruthy();
  });

  it("calls addToolApprovalResponse with approved=true when Allow is clicked", () => {
    const session = makeMockChatSession();
    render(
      <ChatSessionProvider session={session}>
        <ApprovalDialog
          part={{
            type: "tool-delete_strategy",
            toolCallId: "tc-approve-1",
            state: "approval-requested",
            input: { strategy_id: "s_x" },
            approval: { id: "approve-1" },
          }}
        />
      </ChatSessionProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: /allow/i }));
    expect(session.addToolApprovalResponse).toHaveBeenCalledWith({
      id: "tc-approve-1",
      approved: true,
    });
  });
});
