import type { Step, Strategy, StepKind } from "@pathfinder/shared";

export type { Step, Strategy };

export type StrategyNode = {
  id: string;
  kind?: StepKind;
  displayName?: string;
  searchName?: string;
  operator?: string;
  parameters?: Record<string, unknown>;
  recordType?: string;
  wdkStepId?: number;
  selected?: boolean;
};

export type StrategyEdge = {
  sourceId: string;
  targetId: string;
  kind: "primary" | "secondary";
};

export type StrategyGraphSelection = {
  graphId?: string;
  nodeIds: string[];
  selectedNodeIds: string[];
  contextNodeIds: string[];
  nodes: StrategyNode[];
  edges: StrategyEdge[];
};
