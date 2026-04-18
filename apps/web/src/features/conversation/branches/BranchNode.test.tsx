/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReactFlowProvider } from "@xyflow/react";
import { NuqsTestingAdapter } from "nuqs/adapters/testing";
import type { CheckpointNode } from "@pathfinder/shared/generated/types/CheckpointNode";
import { BranchNode } from "./BranchNode";

vi.mock("@/lib/api/client", () => ({
  client: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

function makeData(overrides: Partial<CheckpointNode> = {}): CheckpointNode {
  return {
    checkpointId: "cp1",
    parentCheckpointId: null,
    threadId: "t1",
    source: "loop",
    step: 3,
    node: "discovery",
    createdAt: "",
    ...overrides,
  };
}

function renderNode(data: CheckpointNode, selected = false) {
  return render(
    <NuqsTestingAdapter>
      <ReactFlowProvider>
        <BranchNode
          id="cp1"
          type="checkpointNode"
          data={data}
          selected={selected}
          isConnectable={false}
          positionAbsoluteX={0}
          positionAbsoluteY={0}
          zIndex={0}
          dragging={false}
          dragHandle=""
          parentId=""
          width={220}
          height={60}
          deletable={false}
          selectable={true}
          draggable={false}
        />
      </ReactFlowProvider>
    </NuqsTestingAdapter>,
  );
}

describe("BranchNode", () => {
  it("renders the phase name and step number", () => {
    renderNode(makeData());
    expect(screen.getByText("discovery")).toBeInTheDocument();
    expect(screen.getByText("step 3")).toBeInTheDocument();
  });

  it("shows source icon for input type", () => {
    renderNode(makeData({ source: "input" }));
    expect(screen.getByText("⬇")).toBeInTheDocument();
  });

  it("shows source icon for fork type", () => {
    renderNode(makeData({ source: "fork" }));
    expect(screen.getByText("⎇")).toBeInTheDocument();
  });

  it("shows source icon for update type", () => {
    renderNode(makeData({ source: "update" }));
    expect(screen.getByText("⭑")).toBeInTheDocument();
  });

  it("shows loop icon by default", () => {
    renderNode(makeData({ source: "loop" }));
    expect(screen.getByText("·")).toBeInTheDocument();
  });

  it("renders a label when present", () => {
    renderNode(makeData({ label: "Breakthrough" }));
    expect(screen.getByText("Breakthrough")).toBeInTheDocument();
  });

  it("does not render label when absent", () => {
    renderNode(makeData({ label: null }));
    expect(screen.queryByText("Breakthrough")).not.toBeInTheDocument();
  });

  it("shows dash for null node name", () => {
    renderNode(makeData({ node: null }));
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("applies selected border class when selected", () => {
    const { container } = renderNode(makeData(), true);
    const nodeDiv = container.querySelector("[data-branch-node]");
    expect(nodeDiv?.className).toContain("border-primary");
  });

  it("applies default border class when not selected", () => {
    const { container } = renderNode(makeData(), false);
    const nodeDiv = container.querySelector("[data-branch-node]");
    expect(nodeDiv?.className).toContain("border-border");
  });

  it("shows fork button when selected", () => {
    renderNode(makeData(), true);
    expect(
      screen.getByRole("button", { name: /fork/i }),
    ).toBeInTheDocument();
  });

  it("hides fork button when not selected", () => {
    renderNode(makeData(), false);
    expect(
      screen.queryByRole("button", { name: /fork/i }),
    ).not.toBeInTheDocument();
  });
});
