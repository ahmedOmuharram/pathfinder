// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { UIMessage } from "ai";
import type { PlanArtifact } from "@pathfinder/shared";

const submitProductActionMock = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
vi.mock("@pathfinder/shared/generated/hooks/useSubmitProductAction", () => ({
  submitProductAction: submitProductActionMock,
}));

import { ChatHelpersProvider, type ChatHelpers } from "../runtime/chatHelpersContext";
import { PlanPanel } from "./PlanPanel";

function makePlan(planId: string): PlanArtifact {
  return { planId, rationale: `rationale ${planId}`, steps: [] };
}

function makePlanWithSlot(planId: string): PlanArtifact {
  return {
    planId,
    rationale: `rationale ${planId}`,
    steps: [],
    slots: [
      {
        stepId: "step_1",
        paramName: "hard_floor",
        paramType: "number-enum",
        status: "needs_user_input",
        required: true,
        question: "Pick a read-floor tier",
        context: "",
        options: [
          { label: "1693 reads", value: "1693.23" },
          { label: "6772 reads", value: "6772.93" },
        ],
      },
    ],
  };
}

function planArtifactPart(plan: PlanArtifact) {
  return { type: "data-plan-artifact" as const, data: plan };
}

function approvalPart(opts: { approvalId?: string; planId?: string }) {
  return {
    type: "tool-submit_plan_for_approval" as const,
    toolCallId: "call-1",
    state: "approval-requested" as const,
    input: { planId: opts.planId ?? "p1" },
    approval: { id: opts.approvalId ?? "a1" },
  };
}

function makeAssistantMessage(parts: unknown[], id = "asst-1"): UIMessage {
  return { id, role: "assistant", parts } as unknown as UIMessage;
}

function makeChat(messages: UIMessage[]): ChatHelpers {
  let mutableMessages = messages;
  return {
    get messages() {
      return mutableMessages;
    },
    addToolApprovalResponse: vi.fn(),
    sendMessage: vi.fn(),
    setMessages: vi.fn((updater: UIMessage[] | ((m: UIMessage[]) => UIMessage[])) => {
      mutableMessages =
        typeof updater === "function" ? updater(mutableMessages) : updater;
    }),
  } as unknown as ChatHelpers;
}

function renderPanel(messages: UIMessage[] = []) {
  const chat = makeChat(messages);
  const utils = render(
    <ChatHelpersProvider value={chat}>
      <PlanPanel />
    </ChatHelpersProvider>,
  );
  return { ...utils, chat };
}

beforeEach(() => {
  submitProductActionMock.mockClear();
});

afterEach(() => cleanup());

describe("PlanPanel — render-state matrix", () => {
  it("empty: shows 'No plan proposed yet' when no plan parts", () => {
    renderPanel();
    expect(screen.getByText(/no plan proposed yet/i)).toBeInTheDocument();
  });

  it("draft (plan but no approval-requested): shows plan, hides buttons, shows view-only", () => {
    renderPanel([makeAssistantMessage([planArtifactPart(makePlan("p1"))])]);
    expect(screen.getByText("rationale p1")).toBeInTheDocument();
    expect(screen.queryByTestId("plan-approve")).toBeNull();
    expect(screen.queryByTestId("plan-deny")).toBeNull();
    expect(screen.getByText(/view only/i)).toBeInTheDocument();
  });

  it("submitted (pending on latest): shows all 4 actions", () => {
    renderPanel([
      makeAssistantMessage([
        planArtifactPart(makePlan("p1")),
        approvalPart({ planId: "p1" }),
      ]),
    ]);
    expect(screen.getByTestId("plan-approve")).toBeInTheDocument();
    expect(screen.getByTestId("plan-deny")).toBeInTheDocument();
    expect(screen.getByTestId("plan-suggest-toggle")).toBeInTheDocument();
    expect(screen.getByTestId("plan-ask-toggle")).toBeInTheDocument();
  });

  it("multi-version, focus on older: hides action buttons", () => {
    renderPanel([
      makeAssistantMessage([
        planArtifactPart(makePlan("p1")),
        planArtifactPart(makePlan("p2")),
        approvalPart({ planId: "p2" }),
      ]),
    ]);
    fireEvent.click(screen.getByLabelText("Previous plan"));
    expect(screen.queryByTestId("plan-approve")).toBeNull();
    expect(screen.getByText(/older plan/i)).toBeInTheDocument();
  });

  it("carousel nav renders when count > 1", () => {
    renderPanel([
      makeAssistantMessage([
        planArtifactPart(makePlan("p1")),
        planArtifactPart(makePlan("p2")),
      ]),
    ]);
    expect(screen.getByTestId("plan-carousel-nav")).toBeInTheDocument();
    expect(screen.getByText(/v2 of 2/i)).toBeInTheDocument();
  });

  it("carousel nav clicking previous moves focus", () => {
    renderPanel([
      makeAssistantMessage([
        planArtifactPart(makePlan("p1")),
        planArtifactPart(makePlan("p2")),
      ]),
    ]);
    expect(screen.getByText(/v2 of 2/i)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Previous plan"));
    expect(screen.getByText(/v1 of 2/i)).toBeInTheDocument();
  });
});

describe("PlanPanel — slot-filling form (Stage A)", () => {
  it("renders form fields for needs_user_input slots", () => {
    renderPanel([
      makeAssistantMessage([
        planArtifactPart(makePlanWithSlot("p1")),
        approvalPart({ planId: "p1" }),
      ]),
    ]);
    expect(screen.getByTestId("plan-slot-forms")).toBeInTheDocument();
    expect(screen.getByTestId("slot-field-step_1-hard_floor")).toBeInTheDocument();
    expect(screen.getByText("Pick a read-floor tier")).toBeInTheDocument();
  });

  it("disables Approve until user picks a value for needs_user_input slots", () => {
    renderPanel([
      makeAssistantMessage([
        planArtifactPart(makePlanWithSlot("p1")),
        approvalPart({ planId: "p1" }),
      ]),
    ]);
    const approve = screen.getByTestId("plan-approve");
    expect(approve).toBeDisabled();
  });

  it("Approve sends slot answers via setMessages + addToolApprovalResponse", () => {
    const { chat } = renderPanel([
      makeAssistantMessage(
        [
          planArtifactPart(makePlanWithSlot("p1")),
          approvalPart({ approvalId: "a1", planId: "p1" }),
        ],
        "asst-1",
      ),
    ]);
    fireEvent.click(screen.getByText("Select an option…"));
    fireEvent.click(screen.getByTestId("slot-option-1693 reads"));
    const approve = screen.getByTestId("plan-approve");
    expect(approve).not.toBeDisabled();
    fireEvent.click(approve);
    expect(chat.setMessages).toHaveBeenCalled();
    expect(chat.addToolApprovalResponse).toHaveBeenCalledWith({
      id: "a1",
      approved: true,
    });
    const updatedAsst = chat.messages.find((m) => m.id === "asst-1");
    expect(updatedAsst).toBeDefined();
    const slotAnswerPart = updatedAsst?.parts.find(
      (p) => (p as { type?: string }).type === "data-plan-slot-answers",
    );
    expect(slotAnswerPart).toBeDefined();
    const data = (slotAnswerPart as { data?: unknown }).data as {
      toolCallId: string;
      answers: Array<{ stepId: string; paramName: string; value: unknown }>;
    };
    expect(data.toolCallId).toBe("a1");
    expect(data.answers).toEqual([
      { stepId: "step_1", paramName: "hard_floor", value: "1693.23" },
    ]);
  });
});

describe("PlanPanel — product-action wiring + SDK v6", () => {
  it("Approve: addToolApprovalResponse({approved:true}) + plan_approve telemetry", () => {
    const { chat } = renderPanel([
      makeAssistantMessage(
        [
          planArtifactPart(makePlan("p1")),
          approvalPart({ approvalId: "a1", planId: "p1" }),
        ],
        "asst-1",
      ),
    ]);
    fireEvent.click(screen.getByTestId("plan-approve"));
    expect(chat.addToolApprovalResponse).toHaveBeenCalledWith({
      id: "a1",
      approved: true,
    });
    expect(submitProductActionMock).toHaveBeenCalledWith(
      expect.objectContaining({
        action: "plan_approve",
        streamId: "asst-1",
        planId: "p1",
      }),
    );
  });

  it("Deny: addToolApprovalResponse({approved:false}) + plan_reject telemetry", () => {
    const { chat } = renderPanel([
      makeAssistantMessage([
        planArtifactPart(makePlan("p1")),
        approvalPart({ approvalId: "a1", planId: "p1" }),
      ]),
    ]);
    fireEvent.click(screen.getByTestId("plan-deny"));
    expect(chat.addToolApprovalResponse).toHaveBeenCalledWith({
      id: "a1",
      approved: false,
    });
    expect(submitProductActionMock).toHaveBeenCalledWith(
      expect.objectContaining({ action: "plan_reject" }),
    );
  });

  it("Suggest changes: sendMessage + plan_suggest_changes telemetry with metadata.text", () => {
    const { chat } = renderPanel([
      makeAssistantMessage([
        planArtifactPart(makePlan("p1")),
        approvalPart({ planId: "p1" }),
      ]),
    ]);
    fireEvent.click(screen.getByTestId("plan-suggest-toggle"));
    fireEvent.change(screen.getByTestId("plan-suggest-input"), {
      target: { value: "use lower threshold" },
    });
    fireEvent.click(screen.getByTestId("plan-suggest-send"));
    expect(chat.sendMessage).toHaveBeenCalledWith({ text: "use lower threshold" });
    expect(submitProductActionMock).toHaveBeenCalledWith(
      expect.objectContaining({
        action: "plan_suggest_changes",
        metadata: { text: "use lower threshold" },
      }),
    );
  });

  it("Ask question: sendMessage + plan_ask_question telemetry with metadata.text", () => {
    const { chat } = renderPanel([
      makeAssistantMessage([
        planArtifactPart(makePlan("p1")),
        approvalPart({ planId: "p1" }),
      ]),
    ]);
    fireEvent.click(screen.getByTestId("plan-ask-toggle"));
    fireEvent.change(screen.getByTestId("plan-ask-input"), {
      target: { value: "why this threshold?" },
    });
    fireEvent.click(screen.getByTestId("plan-ask-send"));
    expect(chat.sendMessage).toHaveBeenCalledWith({ text: "why this threshold?" });
    expect(submitProductActionMock).toHaveBeenCalledWith(
      expect.objectContaining({
        action: "plan_ask_question",
        metadata: { text: "why this threshold?" },
      }),
    );
  });

  it("Empty Suggest text: Send button disabled, no telemetry, no message", () => {
    const { chat } = renderPanel([
      makeAssistantMessage([
        planArtifactPart(makePlan("p1")),
        approvalPart({ planId: "p1" }),
      ]),
    ]);
    fireEvent.click(screen.getByTestId("plan-suggest-toggle"));
    const send = screen.getByTestId("plan-suggest-send");
    expect(send).toBeDisabled();
    fireEvent.click(send);
    expect(chat.sendMessage).not.toHaveBeenCalled();
    expect(submitProductActionMock).not.toHaveBeenCalled();
  });

  it("Telemetry failure does not block the underlying action (fire-and-forget)", () => {
    submitProductActionMock.mockRejectedValueOnce(new Error("network"));
    const { chat } = renderPanel([
      makeAssistantMessage([
        planArtifactPart(makePlan("p1")),
        approvalPart({ planId: "p1" }),
      ]),
    ]);
    fireEvent.click(screen.getByTestId("plan-approve"));
    expect(chat.addToolApprovalResponse).toHaveBeenCalled();
  });
});
