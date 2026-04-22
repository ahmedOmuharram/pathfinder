// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Step, Strategy } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/strategy/store";
import { SearchNode } from "./SearchNode";
import type { StepNodeProps } from "./types";

vi.mock("@xyflow/react", async () => {
  const React = await import("react");
  return {
    Handle: ({ id, type }: { id?: string; type: string }) =>
      React.createElement("span", {
        "data-testid": `flow-handle-${type}-${id ?? "default"}`,
      }),
    NodeToolbar: ({ children }: { children?: React.ReactNode }) =>
      React.createElement("div", { "data-testid": "node-toolbar" }, children),
    Position: { Top: "top", Right: "right", Bottom: "bottom", Left: "left" },
  };
});

function makeStep(overrides: Partial<Step> = {}): Step {
  return {
    id: "s1",
    kind: "search",
    displayName: "Genes by taxon",
    searchName: "GenesByTaxon",
    recordType: "gene",
    parameters: { organism: "Plasmodium" },
    estimatedSize: 1234,
    isBuilt: false,
    isFiltered: false,
    validation: null,
    ...overrides,
  } as Step;
}

function makeStrategy(steps: Step[]): Strategy {
  return {
    id: "draft",
    name: "Test",
    siteId: "plasmodb",
    recordType: "gene",
    steps,
    rootStepId: steps[0]?.id ?? null,
    isSaved: false,
    description: null,
    wdkStrategyId: null,
    wdkUrl: null,
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
  };
}

function reset() {
  useStrategyStore.setState({
    strategy: null,
    stepLifecycleById: {},
    undoStack: [],
    redoStack: [],
  });
}

function defaultProps(step: Step): StepNodeProps {
  return {
    step,
    selected: false,
    showOutputHandle: true,
    showPrimaryInputHandle: false,
    showSecondaryInputHandle: false,
  };
}

describe("SearchNode", () => {
  beforeEach(reset);

  it("renders the step name and result count", () => {
    const step = makeStep({ estimatedSize: 1234 });
    useStrategyStore.getState().setStrategy(makeStrategy([step]));
    render(<SearchNode {...defaultProps(step)} />);
    expect(screen.getByText("Genes by taxon")).toBeTruthy();
    expect(screen.getByText(/1,234/)).toBeTruthy();
  });

  it("shows a shimmer skeleton while count is loading", () => {
    const step = makeStep({ estimatedSize: null });
    useStrategyStore.getState().setStrategy(makeStrategy([step]));
    useStrategyStore.getState().initStepLifecycle("s1");
    useStrategyStore
      .getState()
      .dispatchStepEvent("s1", { type: "VALIDATE" });
    const { container } = render(<SearchNode {...defaultProps(step)} />);
    expect(
      container.querySelector('[data-slot="skeleton"]'),
    ).not.toBeNull();
  });

  it("shows validation error treatment with left border + corner dot", () => {
    const step = makeStep({ estimatedSize: null });
    useStrategyStore.getState().setStrategy(makeStrategy([step]));
    useStrategyStore
      .getState()
      .applyStepValidationErrors({ s1: "Missing organism" });
    const { container } = render(<SearchNode {...defaultProps(step)} />);
    expect(
      container.querySelector('[data-validation="error"]'),
    ).not.toBeNull();
    expect(
      container.querySelector('[data-corner-dot="error"]'),
    ).not.toBeNull();
  });

  it("renders an output handle on the right when allowed", () => {
    const step = makeStep();
    useStrategyStore.getState().setStrategy(makeStrategy([step]));
    render(<SearchNode {...defaultProps(step)} />);
    expect(screen.getByTestId("flow-handle-source-right")).toBeTruthy();
  });
});
