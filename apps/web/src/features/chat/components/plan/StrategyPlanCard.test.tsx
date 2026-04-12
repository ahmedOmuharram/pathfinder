// @vitest-environment jsdom

import type { ReactElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ParamSpec } from "@pathfinder/shared";

import { useParamSpecs } from "@/lib/hooks/useParamSpecs";
import type { InteractivePlan } from "@/lib/types/plan";
import { useSessionStore } from "@/state/useSessionStore";
import { StrategyPlanCard } from "./StrategyPlanCard";

vi.mock("@/lib/hooks/useParamSpecs", () => ({
  useParamSpecs: vi.fn(),
}));
vi.mock("@/lib/api/feedback", () => ({
  submitProductAction: vi.fn(() => Promise.resolve()),
}));

import { submitProductAction } from "@/lib/api/feedback";

const basePlan: InteractivePlan = {
  id: "plan_1",
  title: "Approval Test Plan",
  description: "Test plan",
  rationale: "Test rationale",
  status: "presented",
  version: 1,
  steps: [
    {
      id: "step_1",
      searchName: "GenesByTaxon",
      displayName: "Genes by Taxon",
      recordType: "transcript",
      rationale: "",
      stepType: "leaf",
      status: "ready",
      parameters: {},
      operator: null,
      expectedCount: null,
      actualCount: null,
      wdkStepId: null,
      graphStepId: null,
    },
  ],
  connections: [],
  questions: [],
  uncertainties: [],
  createdAt: "",
  updatedAt: "",
};

const mockUseParamSpecs = vi.mocked(useParamSpecs);
const mockSubmitProductAction = vi.mocked(submitProductAction);

function renderWithProviders(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

beforeEach(() => {
  class MockIntersectionObserver {
    observe() {}
    disconnect() {}
  }
  vi.stubGlobal("IntersectionObserver", MockIntersectionObserver);
  useSessionStore.setState({ strategyId: "strategy-123" });
});

describe("StrategyPlanCard", () => {
  beforeEach(() => {
    mockUseParamSpecs.mockReturnValue({ paramSpecs: [], isLoading: false });
    mockSubmitProductAction.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it("approves via structured plan action instead of sending a chat message", async () => {
    const onSendMessage = vi.fn();
    const onApprovePlan = vi.fn(async () => {});

    renderWithProviders(
      <StrategyPlanCard
        siteId="plasmodb"
        plan={basePlan}
        planTraceId="trace-plan-1"
        planMessageGroupId="group-plan-1"
        onSendMessage={onSendMessage}
        onApprovePlan={onApprovePlan}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Approve & Execute" }));

    expect(onApprovePlan).toHaveBeenCalledWith({
      action: "approve",
      planId: "plan_1",
      traceId: "trace-plan-1",
      messageGroupId: "group-plan-1",
      source: "plan_panel",
      paramEdits: [],
      answers: [],
    });
    expect(onSendMessage).not.toHaveBeenCalled();
  });

  it("renders WDK vocabulary parameters as typed controls and approves canonical values", async () => {
    const onSendMessage = vi.fn();
    const onApprovePlan = vi.fn(async () => {});
    const organismSpec = {
      name: "organism",
      displayName: "Organism",
      type: "single-pick-vocabulary",
      displayType: "checkBox",
      allowEmptyValue: false,
      allowMultipleValues: false,
      countOnlyLeaves: false,
      initialDisplayValue: "pfal",
      vocabulary: [
        { value: "pfal", label: "P. falciparum" },
        { value: "pvivax", label: "P. vivax" },
      ],
      isNumber: false,
    } as ParamSpec;
    const planWithVocabParam: InteractivePlan = {
      ...basePlan,
      steps: [
        {
          ...basePlan.steps[0]!,
          status: "needs_user_input",
          parameters: {
            organism: {
              name: "organism",
              displayName: "Organism",
              paramType: "string",
              value: "pfal",
              status: "set",
              required: true,
              description: null,
              constraints: null,
              dependsOn: [],
              vocabularySummary: null,
              question: null,
              options: null,
              rationale: null,
            },
          },
        },
      ],
    };
    mockUseParamSpecs.mockReturnValue({
      paramSpecs: [organismSpec],
      isLoading: false,
    });

    renderWithProviders(
      <StrategyPlanCard
        siteId="plasmodb"
        plan={planWithVocabParam}
        planTraceId="trace-plan-1"
        planMessageGroupId="group-plan-1"
        onSendMessage={onSendMessage}
        onApprovePlan={onApprovePlan}
      />,
    );

    const falciparum = screen.getByLabelText("P. falciparum");
    const vivax = screen.getByLabelText("P. vivax");
    expect(falciparum).toMatchObject({ type: "radio", checked: true });

    fireEvent.click(vivax);
    fireEvent.click(screen.getByRole("button", { name: "Approve & Execute" }));

    expect(onApprovePlan).toHaveBeenCalledWith({
      action: "approve",
      planId: "plan_1",
      traceId: "trace-plan-1",
      messageGroupId: "group-plan-1",
      source: "plan_panel",
      paramEdits: [
        { stepId: "step_1", paramName: "organism", newValue: "pvivax" },
      ],
      answers: [],
    });
  });

  it("records a product action before asking a plan question", async () => {
    const onSendMessage = vi.fn();
    const onApprovePlan = vi.fn(async () => {});

    renderWithProviders(
      <StrategyPlanCard
        siteId="plasmodb"
        plan={basePlan}
        planTraceId="trace-plan-1"
        planMessageGroupId="group-plan-1"
        onSendMessage={onSendMessage}
        onApprovePlan={onApprovePlan}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Ask a Question" }));

    expect(mockSubmitProductAction).toHaveBeenCalledWith({
      action: "plan_ask_question",
      streamId: "strategy-123",
      strategyId: "strategy-123",
      planId: "plan_1",
      traceId: "trace-plan-1",
      messageGroupId: "group-plan-1",
      metadata: {
        source: "plan_panel",
        unansweredQuestionCount: 0,
        paramEditCount: 0,
      },
    });
    expect(onSendMessage).toHaveBeenCalledWith(
      "I have a question about this plan:",
      {
        action: "plan_ask_question",
        source: "plan_panel",
        planId: "plan_1",
        planTraceId: "trace-plan-1",
        planMessageGroupId: "group-plan-1",
        unansweredQuestionCount: 0,
        paramEditCount: 0,
      },
    );
  });

  it("records reject and sends a discard request", async () => {
    const onSendMessage = vi.fn();
    const onApprovePlan = vi.fn(async () => {});

    renderWithProviders(
      <StrategyPlanCard
        siteId="plasmodb"
        plan={basePlan}
        planTraceId="trace-plan-1"
        planMessageGroupId="group-plan-1"
        onSendMessage={onSendMessage}
        onApprovePlan={onApprovePlan}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Reject Plan" }));

    expect(mockSubmitProductAction).toHaveBeenCalledWith({
      action: "plan_reject",
      streamId: "strategy-123",
      strategyId: "strategy-123",
      planId: "plan_1",
      traceId: "trace-plan-1",
      messageGroupId: "group-plan-1",
      metadata: {
        source: "plan_panel",
        planStatus: "presented",
        unansweredQuestionCount: 0,
        paramEditCount: 0,
      },
    });
    expect(onSendMessage).toHaveBeenCalledWith(
      "Please discard this plan and propose a different one for the same goal.",
      {
        action: "plan_reject",
        source: "plan_panel",
        planId: "plan_1",
        planTraceId: "trace-plan-1",
        planMessageGroupId: "group-plan-1",
        unansweredQuestionCount: 0,
        paramEditCount: 0,
        planStatus: "presented",
      },
    );
  });

  it("records regenerate and asks for a fresh plan", async () => {
    const onSendMessage = vi.fn();
    const onApprovePlan = vi.fn(async () => {});

    renderWithProviders(
      <StrategyPlanCard
        siteId="plasmodb"
        plan={basePlan}
        planTraceId="trace-plan-1"
        planMessageGroupId="group-plan-1"
        onSendMessage={onSendMessage}
        onApprovePlan={onApprovePlan}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Regenerate Plan" }));

    expect(mockSubmitProductAction).toHaveBeenCalledWith({
      action: "assistant_regenerate",
      streamId: "strategy-123",
      strategyId: "strategy-123",
      planId: "plan_1",
      traceId: "trace-plan-1",
      messageGroupId: "group-plan-1",
      metadata: {
        source: "plan_panel",
        scope: "plan",
        planStatus: "presented",
        unansweredQuestionCount: 0,
        paramEditCount: 0,
      },
    });
    expect(onSendMessage).toHaveBeenCalledWith(
      "Please regenerate this plan from scratch. Use a different approach if helpful.",
      {
        action: "assistant_regenerate",
        source: "plan_panel",
        planId: "plan_1",
        planTraceId: "trace-plan-1",
        planMessageGroupId: "group-plan-1",
        unansweredQuestionCount: 0,
        paramEditCount: 0,
        scope: "plan",
        planStatus: "presented",
      },
    );
  });
});
