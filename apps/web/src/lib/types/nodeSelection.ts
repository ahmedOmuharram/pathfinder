import type { StepParameters } from "@/lib/strategyGraph/types";

/**
 * A node within a node-selection payload.
 *
 * The fields mirror the `Step` shape used by the strategy graph, with an extra
 * `selected` flag for UI highlighting.
 */
export type NodeSelectionNode = {
  id: string;
  kind?: string | null;
  displayName?: string;
  searchName?: string | null;
  operator?: string | null;
  parameters?: StepParameters | null;
  recordType?: string | null;
  estimatedSize?: number | null;
  wdkStepId?: number | null;
  selected?: boolean;
};

/**
 * An edge within a node-selection payload.
 */
export type NodeSelectionEdge = {
  sourceId: string;
  targetId: string;
  kind: string;
};

export type NodeSelection = {
  graphId?: string;
  nodeIds: string[];
  selectedNodeIds: string[];
  contextNodeIds: string[];
  nodes: NodeSelectionNode[];
  edges: NodeSelectionEdge[];
};
