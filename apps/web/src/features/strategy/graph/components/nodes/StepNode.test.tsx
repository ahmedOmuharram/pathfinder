// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Node, NodeProps } from "@xyflow/react";
import { CombineOperator, type Step } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/strategy/store";
import { StepNode } from "./StepNode";
import type { StepNodeData } from "./types";

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
    parameters: {},
    estimatedSize: 100,
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

function makeNodeProps(
  step: Step,
  selected: boolean,
  extra: Partial<StepNodeData> = {},
): NodeProps<Node<StepNodeData>> {
  return {
    id: step.id,
    type: "step",
    data: {
      step,
      showOutputHandle: true,
      showPrimaryInputHandle: true,
      showSecondaryInputHandle: true,
      ...extra,
    },
    selected,
    dragging: false,
    isConnectable: true,
    positionAbsoluteX: 0,
    positionAbsoluteY: 0,
    zIndex: 0,
    selectable: true,
    deletable: true,
    draggable: true,
  };
}

describe("StepNode dispatcher", () => {
  beforeEach(reset);

  it("dispatches to SearchNode for kind=search", () => {
    const step = makeStep({ kind: "search" });
    const { container } = render(<StepNode {...makeNodeProps(step, false)} />);
    expect(container.querySelector('[data-kind="search"]')).not.toBeNull();
  });

  it("dispatches to CombineNode for kind=combine", () => {
    const step = makeStep({
      kind: "combine",
      operator: CombineOperator.INTERSECT,
      primaryInputStepId: "a",
      secondaryInputStepId: "b",
    });
    const { container } = render(<StepNode {...makeNodeProps(step, false)} />);
    expect(container.querySelector('[data-kind="combine"]')).not.toBeNull();
  });

  it("dispatches to TransformNode for kind=transform", () => {
    const step = makeStep({
      kind: "transform",
      primaryInputStepId: "a",
    });
    const { container } = render(<StepNode {...makeNodeProps(step, false)} />);
    expect(container.querySelector('[data-kind="transform"]')).not.toBeNull();
  });

  it("renders a selection ring on the shell when selected=true", () => {
    const step = makeStep();
    const { container } = render(<StepNode {...makeNodeProps(step, true)} />);
    expect(
      container.querySelector('[data-selected="true"]'),
    ).not.toBeNull();
  });

  it("renders the hover-revealed action chips (edit, add to chat, more)", () => {
    const step = makeStep();
    render(
      <StepNode
        {...makeNodeProps(step, false, {
          onAddToChat: () => {},
          onOpenDetails: () => {},
        })}
      />,
    );
    expect(screen.getByTestId(`rf-edit-${step.id}`)).toBeTruthy();
    expect(screen.getByTestId(`rf-add-to-chat-${step.id}`)).toBeTruthy();
    expect(screen.getByTestId(`rf-more-${step.id}`)).toBeTruthy();
  });

  it("tags the rendered node with data-orphan when isOrphan is true", () => {
    const step = makeStep();
    const { container } = render(
      <StepNode {...makeNodeProps(step, false, { isOrphan: true })} />,
    );
    expect(
      container.querySelector('[data-orphan="true"]'),
    ).not.toBeNull();
  });

  it("data-orphan is false by default", () => {
    const step = makeStep();
    const { container } = render(<StepNode {...makeNodeProps(step, false)} />);
    expect(
      container.querySelector('[data-orphan="true"]'),
    ).toBeNull();
    expect(
      container.querySelector('[data-orphan="false"]'),
    ).not.toBeNull();
  });
});
