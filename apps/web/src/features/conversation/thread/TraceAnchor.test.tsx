/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { UIMessage } from "ai";
import { reduceSnapshot, type MessagePart } from "@pathfinder/assistant-client";

import { useSettingsStore } from "@/state/useSettingsStore";

import { ChatHelpersProvider, type ChatHelpers } from "../runtime/chatHelpersContext";
import { SubAgentTraceAnchor, TraceAnchor } from "./TraceAnchor";
import recordedTurn from "@/acceptance/thread/recordedTurn.json";

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn(), message: vi.fn() },
  Toaster: () => null,
}));

const ROW_LABELS = [
  "Search eda studies",
  "Open eda analysis",
  "Search catalog",
  "Set criterion",
  "Preview eda subset",
  "Run control tests",
  "Optimize parameters",
];

function turnParts(): MessagePart[] {
  const assistant = reduceSnapshot(recordedTurn as unknown[]).find(
    (message) => message.role === "assistant",
  );
  if (assistant === undefined) throw new Error("the recorded turn holds no message");
  return assistant.parts;
}

function chatWith(parts: MessagePart[]): ChatHelpers {
  const message: UIMessage = { id: "m1", role: "assistant", parts };
  return {
    id: "conv-1",
    messages: [message],
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

function anchorFor(toolCallId: string, toolName: string, parts = turnParts()) {
  useSettingsStore.setState({ showRawToolCalls: false, showTokenUsage: true });
  return render(
    <ChatHelpersProvider value={chatWith(parts)}>
      <TraceAnchor
        toolName={toolName}
        toolCallId={toolCallId}
        args={{}}
        result={undefined}
        status={{ type: "complete" }}
      />
    </ChatHelpersProvider>,
  );
}

describe("TraceAnchor", () => {
  it("draws the whole run once, at the run's first row-bearing part", () => {
    const view = anchorFor("call_1", "search_eda_studies");
    expect(view.getAllByTestId("turn-trace")).toHaveLength(1);
    const rows = view.getAllByTestId("trace-row");
    expect(rows).toHaveLength(7);
    expect(rows.map((node) => node.textContent)).toEqual(
      expect.arrayContaining([expect.stringContaining("Search eda studies")]),
    );
    ROW_LABELS.forEach((label, index) => {
      expect(rows[index]).toHaveTextContent(label);
    });
  });

  it("draws nothing at any later tool call of the same run", () => {
    for (const id of ["call_2", "call_3", "call_4", "call_5"]) {
      const view = anchorFor(id, "open_eda_analysis");
      expect(view.container.innerHTML).toBe("");
      view.unmount();
    }
  });

  it("draws nothing at a sub-agent call that did not open the run", () => {
    const view = render(
      <ChatHelpersProvider value={chatWith(turnParts())}>
        <SubAgentTraceAnchor
          data={{
            toolCallId: "sa_1",
            subAgent: "frame_problem",
            phase: "frame",
            state: "completed",
          }}
        />
      </ChatHelpersProvider>,
    );
    expect(view.container.innerHTML).toBe("");
  });

  it("labels the run's three groups through the shared phase labels", () => {
    const view = anchorFor("call_1", "search_eda_studies");
    expect(view.getAllByTestId("trace-group-label").map((n) => n.textContent)).toEqual([
      "Lead",
      "Frame",
      "Lead",
    ]);
  });

  it("carries the approval the run is waiting on", () => {
    const view = anchorFor("call_1", "search_eda_studies");
    expect(view.getAllByTestId("approval-card")).toHaveLength(1);
    expect(view.getByTestId("approval-card-title")).toHaveTextContent(
      "Optimize parameters needs your approval before it runs.",
    );
  });

  it("names no figure, no notice and no task among its rows", () => {
    const view = anchorFor("call_1", "search_eda_studies");
    const text = view.getAllByTestId("trace-row").map((node) => node.textContent);
    expect(text.join(" ")).not.toContain("eda.viz");
    expect(text.join(" ")).not.toContain("turn-failed");
    expect(view.queryAllByTestId("figure")).toHaveLength(0);
    expect(view.queryAllByTestId("task-row")).toHaveLength(0);
  });

  it("puts no call JSON in the thread while the dev flag is off", () => {
    const view = anchorFor("call_1", "search_eda_studies");
    expect(view.container.textContent).not.toContain("wdkStepId");
    expect(view.container.textContent).not.toContain("datasetId");
  });

  it("draws its own single row when no chat runtime is around it", () => {
    useSettingsStore.setState({ showRawToolCalls: false, showTokenUsage: true });
    render(
      <TraceAnchor
        toolName="set_criterion"
        toolCallId="call_9"
        args={{ criterionId: "c1" }}
        result={undefined}
        status={{ type: "running" }}
      />,
    );
    const rows = screen.getAllByTestId("trace-row");
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveTextContent("Set criterion");
    expect(screen.getByTestId("tool-call-part")).toBeInTheDocument();
    expect(screen.getByTestId("turn-trace-summary")).toHaveTextContent("Working...");
  });

  it("draws the sub-agent's own group when no chat runtime is around it", () => {
    useSettingsStore.setState({ showRawToolCalls: false, showTokenUsage: true });
    render(
      <SubAgentTraceAnchor
        data={{
          toolCallId: "sa_9",
          subAgent: "frame_problem",
          phase: "frame",
          state: "started",
        }}
      />,
    );
    expect(screen.getByTestId("data-sub-agent-call")).toBeInTheDocument();
    expect(screen.getByTestId("trace-group-label")).toHaveTextContent("Frame");
  });

  it("draws no group for a dispatch payload the wire's schema refuses", () => {
    const view = render(
      <SubAgentTraceAnchor
        data={{ subAgent: "frame_problem", phase: "frame", state: "started" } as never}
      />,
    );
    expect(view.container.innerHTML).toBe("");
  });

  it("draws no row for a summary the wire's schema refuses", () => {
    // A summary the wire's schema refuses: the field is not a string.
    const malformed = {
      type: "tool-set_criterion",
      toolCallId: "call_x",
      state: "output-available",
      input: {},
      output: { ok: true },
      summary: 42,
    } as unknown as MessagePart;
    const parts: MessagePart[] = [malformed];
    const view = render(
      <ChatHelpersProvider value={chatWith(parts)}>
        <TraceAnchor
          toolName="set_criterion"
          toolCallId="call_x"
          args={{}}
          result={undefined}
          status={{ type: "complete" }}
        />
      </ChatHelpersProvider>,
    );
    expect(view.getAllByTestId("trace-row")).toHaveLength(1);
    expect(view.queryAllByTestId("trace-row-summary")).toHaveLength(0);
  });
});
