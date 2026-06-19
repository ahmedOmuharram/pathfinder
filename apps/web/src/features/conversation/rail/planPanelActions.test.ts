import { describe, expect, it, vi, beforeEach } from "vitest";
import type { UIMessage } from "ai";

import {
  handleApprove,
  handleDeny,
  handleSuggestChanges,
  type ChatHelpersForApproval,
  type PendingApprovalInfo,
} from "./planPanelActions";

vi.mock("@pathfinder/shared/generated/hooks/useSubmitProductAction", () => ({
  submitProductAction: vi.fn().mockResolvedValue(undefined),
}));

const resolvePendingApproval = vi.fn();
vi.mock("@/state/usePlanStore", () => ({
  usePlanStore: { getState: () => ({ resolvePendingApproval }) },
}));

function makeChat() {
  const chat = {
    addToolApprovalResponse: vi.fn(),
    sendMessage: vi.fn(),
    setMessages: vi.fn(),
  };
  return chat satisfies ChatHelpersForApproval;
}

const pending: PendingApprovalInfo = {
  approvalId: "appr-1",
  planId: "p1",
  sourceMessage: { id: "m1", role: "assistant", parts: [] } as unknown as UIMessage,
};

describe("plan approval actions", () => {
  beforeEach(() => {
    resolvePendingApproval.mockClear();
  });

  it("approve resolves the deferred tool as approved", () => {
    const chat = makeChat();
    handleApprove(chat, pending);
    expect(chat.addToolApprovalResponse).toHaveBeenCalledWith({
      id: "appr-1",
      approved: true,
    });
  });

  it("deny resolves the deferred tool as not-approved", () => {
    const chat = makeChat();
    handleDeny(chat, pending);
    expect(chat.addToolApprovalResponse).toHaveBeenCalledWith({
      id: "appr-1",
      approved: false,
    });
  });

  it("request-changes resolves the approval (denied) with the change text — never leaves it pending", () => {
    const chat = makeChat();
    handleSuggestChanges(chat, pending, "broaden the kinase search");
    expect(chat.addToolApprovalResponse).toHaveBeenCalledWith({
      id: "appr-1",
      approved: false,
      reason: "broaden the kinase search",
    });
    // The bug this guards: sending a message while leaving the deferred
    // approval unresolved, which hangs the turn.
    expect(chat.sendMessage).not.toHaveBeenCalled();
    expect(resolvePendingApproval).toHaveBeenCalled();
  });
});
