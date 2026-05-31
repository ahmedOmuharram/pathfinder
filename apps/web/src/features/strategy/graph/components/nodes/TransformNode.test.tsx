// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Step } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/strategy/store";
import { TransformNode } from "./TransformNode";
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
    kind: "transform",
    displayName: "Transform: orthologs",
    searchName: "GenesByOrthologPattern",
    recordType: "gene",
    parameters: {},
    primaryInputStepId: "left",
    estimatedSize: 42,
    isBuilt: false,
    isFiltered: false,
    validation: null,
    ...overrides,
  } as Step;
}

function reset() {
  useStrategyStore.setState({
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
    showSecondaryInputHandle: false,
  };
}

describe("TransformNode", () => {
  beforeEach(reset);

  it("applies the chevron clip-path to the surface", () => {
    const step = makeStep();
    const { container } = render(<TransformNode {...defaultProps(step)} />);
    const surface = container.querySelector('[data-clip="chevron-right"]');
    expect(surface).not.toBeNull();
  });

  it("renders one input handle on the left and one output on the right", () => {
    const step = makeStep();
    render(<TransformNode {...defaultProps(step)} />);
    expect(screen.getByTestId("flow-handle-target-left")).toBeTruthy();
    expect(screen.getByTestId("flow-handle-source-right")).toBeTruthy();
  });
});
