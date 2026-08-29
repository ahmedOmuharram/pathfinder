/**
 * @vitest-environment jsdom
 */
import type { UIMessage } from "ai";
import { describe, it, expect } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import type {
  DataSubAgentCallPayload,
  DataSubAgentStepPayload,
} from "@pathfinder/shared";

import {
  ChatHelpersProvider,
  type ChatHelpers,
} from "../../runtime/chatHelpersContext";
import { SubAgentCallCard } from "./SubAgentCallCard";

const DISPATCH: DataSubAgentCallPayload = {
  toolCallId: "lead_call_recover",
  subAgent: "execution",
  phase: "execution",
  state: "completed",
  modelId: "openai:gpt-5.6-luna",
  summary: "",
  tokens: 0,
  costUsd: "0",
};

function stepPart(step: DataSubAgentStepPayload): UIMessage["parts"][number] {
  return { type: "data-sub-agent-step", data: step };
}

function makeChat(messages: UIMessage[]): ChatHelpers {
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
    addToolApprovalResponse: () => {},
    clearError: () => {},
  };
}

function renderCard(terminal: DataSubAgentStepPayload): HTMLElement {
  const chat = makeChat([
    {
      id: "m1",
      role: "assistant",
      parts: [
        stepPart({
          parentToolCallId: "lead_call_recover",
          kind: "tool",
          state: "started",
          toolCallId: "call_delete_step",
          toolName: "delete_step",
          args: { stepId: "s2" },
        }),
        stepPart(terminal),
      ],
    },
  ]);
  render(
    <ChatHelpersProvider value={chat}>
      <SubAgentCallCard data={DISPATCH} />
    </ChatHelpersProvider>,
  );
  // A step result sits two collapsibles deep: the dispatch card, then the step.
  fireEvent.click(screen.getByRole("button"));
  const step = screen.getByRole("button", { name: /Delete step/ });
  fireEvent.click(step);
  return step;
}

describe("SubAgentCallCard step states", () => {
  it("reads Denied, not Error, for a tool call the user refused", () => {
    const step = renderCard({
      parentToolCallId: "lead_call_recover",
      kind: "tool",
      state: "denied",
      toolCallId: "call_delete_step",
      toolName: "delete_step",
      resultSummary: "Keep that step.",
    });

    expect(step).toHaveTextContent("Denied");
    expect(step).not.toHaveTextContent("Error");
    expect(screen.getByText("Result")).toBeInTheDocument();
    expect(screen.getByText("Keep that step.")).toBeInTheDocument();
  });

  it("still reads Error for a tool call that failed", () => {
    const step = renderCard({
      parentToolCallId: "lead_call_recover",
      kind: "tool",
      state: "failed",
      toolCallId: "call_delete_step",
      toolName: "delete_step",
      resultSummary: "TOPOLOGY_ERROR: step s2 has no parent",
    });

    expect(step).toHaveTextContent("Error");
    expect(step).not.toHaveTextContent("Denied");
    expect(screen.getByText("step s2 has no parent")).toBeInTheDocument();
  });
});
