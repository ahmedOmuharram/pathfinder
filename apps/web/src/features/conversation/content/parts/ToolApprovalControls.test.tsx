/**
 * @vitest-environment jsdom
 */
import type { UIMessage } from "ai";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { toast } from "sonner";

import {
  ChatHelpersProvider,
  type ChatHelpers,
} from "../../runtime/chatHelpersContext";
import { ToolApprovalControls, findToolApproval } from "./ToolApprovalControls";

vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));

beforeEach(() => {
  vi.mocked(toast.error).mockClear();
});

function assistantMessage(parts: UIMessage["parts"]): UIMessage {
  return { id: "m1", role: "assistant", parts };
}

function pendingPart(toolType: `tool-${string}`): UIMessage["parts"][number] {
  return {
    type: toolType,
    toolCallId: "call-1",
    state: "approval-requested",
    input: { stepId: "step-7" },
    approval: { id: "appr-1" },
  };
}

function makeChat(
  messages: UIMessage[],
  addToolApprovalResponse: ChatHelpers["addToolApprovalResponse"],
): ChatHelpers {
  return {
    id: "conv-1",
    messages,
    status: "ready",
    error: undefined,
    setMessages: () => {},
    sendMessage: async () => {},
    regenerate: async () => {},
    stop: async () => {},
    resumeStream: async () => {},
    addToolResult: async () => {},
    addToolOutput: async () => {},
    addToolApprovalResponse,
    clearError: () => {},
  };
}

function renderControls(
  parts: UIMessage["parts"],
  respond: ChatHelpers["addToolApprovalResponse"] = () => {},
) {
  const chat = makeChat([assistantMessage(parts)], respond);
  return render(
    <ChatHelpersProvider value={chat}>
      <ToolApprovalControls toolCallId="call-1" />
    </ChatHelpersProvider>,
  );
}

describe("findToolApproval", () => {
  it("reads the approval id, tool name and input off a pending approval part", () => {
    const view = findToolApproval(
      [assistantMessage([pendingPart("tool-delete_step")])],
      "call-1",
    );
    expect(view).not.toBeNull();
    expect(view?.approvalId).toBe("appr-1");
    expect(view?.toolName).toBe("delete_step");
    expect(view?.decision).toBe("pending");
    expect(view?.input).toEqual({ stepId: "step-7" });
  });

  it("reports approved once the SDK marks the part approval-responded", () => {
    const view = findToolApproval(
      [
        assistantMessage([
          {
            type: "tool-clear_strategy",
            toolCallId: "call-1",
            state: "approval-responded",
            input: {},
            approval: { id: "appr-1", approved: true },
          },
        ]),
      ],
      "call-1",
    );
    expect(view?.decision).toBe("approved");
  });

  it("reports denied for a denied response and for a denied output", () => {
    const responded = findToolApproval(
      [
        assistantMessage([
          {
            type: "tool-clear_strategy",
            toolCallId: "call-1",
            state: "approval-responded",
            input: {},
            approval: { id: "appr-1", approved: false },
          },
        ]),
      ],
      "call-1",
    );
    expect(responded?.decision).toBe("denied");

    const output = findToolApproval(
      [
        assistantMessage([
          {
            type: "tool-clear_strategy",
            toolCallId: "call-1",
            state: "output-denied",
            input: {},
            approval: { id: "appr-1", approved: false },
          },
        ]),
      ],
      "call-1",
    );
    expect(output?.decision).toBe("denied");
  });

  it("ignores tool parts that carry no approval and unmatched call ids", () => {
    const parts: UIMessage["parts"] = [
      {
        type: "tool-get_strategy",
        toolCallId: "call-1",
        state: "input-available",
        input: {},
      },
    ];
    expect(findToolApproval([assistantMessage(parts)], "call-1")).toBeNull();
    expect(
      findToolApproval([assistantMessage([pendingPart("tool-delete_step")])], "call-2"),
    ).toBeNull();
  });
});

describe("ToolApprovalControls", () => {
  it("renders the humanized tool name, the input and both buttons while pending", async () => {
    renderControls([pendingPart("tool-delete_step")]);
    expect(screen.getByTestId("tool-approval-controls")).toBeInTheDocument();
    expect(screen.getByText(/Delete step/)).toBeInTheDocument();
    expect(screen.getByTestId("tool-approval-approve")).toBeInTheDocument();
    expect(screen.getByTestId("tool-approval-deny")).toBeInTheDocument();
    const rendered = await screen.findAllByText(
      (_content, element) =>
        element?.tagName === "CODE" && element.textContent.includes("step-7"),
    );
    expect(rendered.length).toBeGreaterThan(0);
  });

  it("approves with the approval id from the part", () => {
    const respond = vi.fn();
    renderControls([pendingPart("tool-optimize_search_parameters")], respond);
    fireEvent.click(screen.getByTestId("tool-approval-approve"));
    expect(respond).toHaveBeenCalledWith({ id: "appr-1", approved: true });
  });

  it("denies with the approval id from the part", () => {
    const respond = vi.fn();
    renderControls([pendingPart("tool-clear_strategy")], respond);
    fireEvent.click(screen.getByTestId("tool-approval-deny"));
    expect(respond).toHaveBeenCalledWith({ id: "appr-1", approved: false });
  });

  it("reports a rejected approval response through toast.error", async () => {
    const respond = vi.fn(() => Promise.reject(new Error("network down")));
    renderControls([pendingPart("tool-delete_step")], respond);
    fireEvent.click(screen.getByTestId("tool-approval-approve"));
    await waitFor(() => {
      expect(vi.mocked(toast.error)).toHaveBeenCalledWith("Approval could not be sent");
    });
  });

  it("renders nothing for consult_user, which the consult carousel owns", () => {
    renderControls([pendingPart("tool-consult_user")]);
    expect(screen.queryByTestId("tool-approval-controls")).not.toBeInTheDocument();
    expect(screen.queryByTestId("tool-approval-decision")).not.toBeInTheDocument();
  });

  it("replaces the buttons with the recorded decision once answered", () => {
    renderControls([
      {
        type: "tool-delete_step",
        toolCallId: "call-1",
        state: "approval-responded",
        input: {},
        approval: { id: "appr-1", approved: false },
      },
    ]);
    expect(screen.queryByTestId("tool-approval-approve")).not.toBeInTheDocument();
    expect(screen.getByTestId("tool-approval-decision")).toHaveTextContent("Denied");
  });

  it("renders nothing when the tool call carries no approval", () => {
    renderControls([
      {
        type: "tool-get_strategy",
        toolCallId: "call-1",
        state: "input-available",
        input: {},
      },
    ]);
    expect(screen.queryByTestId("tool-approval-controls")).not.toBeInTheDocument();
  });
});
