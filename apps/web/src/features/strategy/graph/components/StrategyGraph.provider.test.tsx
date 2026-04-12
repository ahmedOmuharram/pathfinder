// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { Strategy } from "@pathfinder/shared";
import type * as StrategiesApi from "@/lib/api/strategies";
import { createTestWrapper } from "@/lib/query/testing";
import { StrategyGraph } from "./StrategyGraph";

vi.mock("@xyflow/react", async () => {
  const React = await import("react");
  const flowContext = React.createContext(false);

  function useFlowProviderGuard() {
    if (!React.useContext(flowContext)) {
      throw new Error("[React Flow]: provider missing");
    }
  }

  return {
    ReactFlowProvider: ({ children }: { children: React.ReactNode }) =>
      React.createElement(flowContext.Provider, { value: true }, children),
    ReactFlow: ({ children }: { children?: React.ReactNode }) => {
      useFlowProviderGuard();
      return React.createElement("div", { "data-testid": "react-flow" }, children);
    },
    Background: () => React.createElement("div", { "data-testid": "flow-background" }),
    Controls: () => React.createElement("div", { "data-testid": "flow-controls" }),
    MiniMap: () => React.createElement("div", { "data-testid": "flow-minimap" }),
    Panel: ({ children }: { children?: React.ReactNode }) =>
      React.createElement("div", null, children),
    Handle: () => React.createElement("span", { "data-testid": "flow-handle" }),
    NodeToolbar: ({ children }: { children?: React.ReactNode }) =>
      React.createElement("div", null, children),
    useReactFlow: () => {
      useFlowProviderGuard();
      return { fitView: vi.fn() };
    },
    useNodesState: <T,>(initial: T[]) => {
      const [nodes, setNodes] = React.useState<T[]>(initial);
      return [nodes, setNodes, vi.fn()] as const;
    },
    useEdgesState: <T,>(initial: T[]) => {
      const [edges, setEdges] = React.useState<T[]>(initial);
      return [edges, setEdges, vi.fn()] as const;
    },
    ConnectionMode: { Loose: "loose" },
    MarkerType: { ArrowClosed: "arrowclosed" },
    Position: {
      Top: "top",
      Right: "right",
      Bottom: "bottom",
      Left: "left",
    },
    SelectionMode: { Partial: "partial" },
  };
});

vi.mock("@/lib/api/sites", () => ({
  sitesOptions: () => ({
    queryKey: ["sites"],
    queryFn: async () => [],
  }),
}));

vi.mock("@/lib/api/strategies", async (importOriginal) => {
  const actual = await importOriginal<typeof StrategiesApi>();
  return {
    ...actual,
    computeStepCounts: vi.fn(async () => ({ counts: {} })),
    pushStrategy: vi.fn(),
  };
});

const STRATEGY: Strategy = {
  id: "strategy-1",
  name: "Editable strategy",
  siteId: "plasmodb",
  recordType: "gene",
  steps: [
    {
      id: "step_1",
      kind: "search",
      displayName: "Genes by taxon",
      searchName: "GenesByTaxon",
      recordType: "gene",
      parameters: { organism: "Plasmodium falciparum 3D7" },
      isBuilt: false,
      isFiltered: false,
    },
  ],
  rootStepId: "step_1",
  isSaved: false,
  createdAt: "2026-01-01T00:00:00.000Z",
  updatedAt: "2026-01-01T00:00:00.000Z",
};

describe("StrategyGraph React Flow provider boundary", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders graph hooks under ReactFlowProvider", () => {
    const { Wrapper } = createTestWrapper();

    render(
      <Wrapper>
        <StrategyGraph strategy={STRATEGY} siteId="plasmodb" />
      </Wrapper>,
    );

    expect(screen.getByTestId("react-flow")).toBeTruthy();
  });
});
