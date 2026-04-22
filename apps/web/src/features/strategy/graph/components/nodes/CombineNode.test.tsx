// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { CombineOperator, type Step, type Strategy } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/strategy/store";
import { CombineNode } from "./CombineNode";
import type { StepNodeProps } from "./types";

vi.mock("@xyflow/react", async () => {
  const React = await import("react");
  return {
    Handle: ({
      id,
      type,
    }: {
      id?: string;
      type: string;
    }) =>
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
    kind: "combine",
    displayName: "Combined gene set",
    searchName: "__combine__",
    recordType: "gene",
    parameters: {},
    operator: CombineOperator.INTERSECT,
    primaryInputStepId: "left",
    secondaryInputStepId: "right",
    estimatedSize: 2891,
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
    showPrimaryInputHandle: true,
    showSecondaryInputHandle: true,
  };
}

describe("CombineNode", () => {
  beforeEach(reset);

  it("renders a mini-venn matching the operator", () => {
    const step = makeStep({ operator: CombineOperator.INTERSECT });
    useStrategyStore.getState().setStrategy(makeStrategy([step]));
    const { container } = render(<CombineNode {...defaultProps(step)} />);
    const lens = container.querySelector('[data-region="lens"]');
    expect(lens?.getAttribute("data-active")).toBe("true");
    expect(
      container.querySelector('[data-region="left-only"]')?.getAttribute("data-active"),
    ).toBe("false");
  });

  it("re-renders the venn fill when the operator changes", () => {
    const step = makeStep({ operator: CombineOperator.INTERSECT });
    useStrategyStore.getState().setStrategy(makeStrategy([step]));
    const { container, rerender } = render(
      <CombineNode {...defaultProps(step)} />,
    );
    expect(
      container.querySelector('[data-region="lens"]')?.getAttribute("data-active"),
    ).toBe("true");

    const updated = makeStep({ operator: CombineOperator.UNION });
    act(() => {
      useStrategyStore.getState().setStrategy(makeStrategy([updated]));
    });
    rerender(<CombineNode {...defaultProps(updated)} />);

    expect(
      container.querySelector('[data-region="left-only"]')?.getAttribute("data-active"),
    ).toBe("true");
    expect(
      container.querySelector('[data-region="right-only"]')?.getAttribute("data-active"),
    ).toBe("true");
  });

  it("renders two input handles on the left + one output on the right", () => {
    const step = makeStep();
    useStrategyStore.getState().setStrategy(makeStrategy([step]));
    render(<CombineNode {...defaultProps(step)} />);
    expect(screen.getByTestId("flow-handle-target-left")).toBeTruthy();
    expect(screen.getByTestId("flow-handle-target-left-secondary")).toBeTruthy();
    expect(screen.getByTestId("flow-handle-source-right")).toBeTruthy();
  });
});
