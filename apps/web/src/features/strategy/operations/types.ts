import type {
  CombineOperator,
  ColocationParams,
  Step,
  Strategy,
  StrategyStepNode,
} from "@pathfinder/shared";

export type AttachPoint =
  | { mode: "new-root" }
  | { mode: "into-slot"; targetStepId: string; slot: "primary" | "secondary" };

export type DeleteResolution =
  | "collapse-combine"
  | "orphan-sibling"
  | "delete-subtree"
  | "promote-primary"
  | "delete-strategy";

export type DeleteEdgeResolution = "detach" | "collapse";

export type GraphOperation =
  | { kind: "addLeaf"; step: Step; attach: AttachPoint }
  | { kind: "addCombine"; step: Step; leftId: string; rightId: string }
  | {
      kind: "addTransform";
      step: Step;
      inputId: string;
      mode: "before-consumer" | "new-root";
    }
  | {
      kind: "duplicateStep";
      sourceStepId: string;
      duplicateStepId: string;
      combineStepId: string;
      combineDisplayName?: string;
    }
  | { kind: "deleteStep"; stepId: string; resolution: DeleteResolution }
  | {
      kind: "deleteEdge";
      sourceId: string;
      targetId: string;
      slot: "primary" | "secondary";
      resolution: DeleteEdgeResolution;
    }
  | { kind: "replaceSubtree"; stepId: string; subtree: Step[] }
  | { kind: "updateStepParams"; stepId: string; parameters: Record<string, unknown> }
  | {
      kind: "updateCombineOperator";
      stepId: string;
      operator: CombineOperator;
      colocationParams?: ColocationParams | null;
    }
  | { kind: "updateStepMeta"; stepId: string; displayName: string }
  | {
      kind: "updateStrategyMeta";
      name?: string;
      description?: string | null;
    }
  | {
      kind: "wireInput";
      targetStepId: string;
      slot: "primary" | "secondary";
      sourceStepId: string;
    }
  | {
      kind: "replaceStrategy";
      root: StrategyStepNode;
      name?: string;
      description?: string | null;
    };

export interface OperationChoice<R extends string = string> {
  resolution: R;
  title: string;
  description: string;
  isDefault: boolean;
  willDelete: string[];
  willOrphan: string[];
}

export type ApplyResult =
  | { kind: "applied"; next: Strategy; description: string }
  | {
      kind: "needs-choice";
      choices: OperationChoice<DeleteResolution | DeleteEdgeResolution>[];
    }
  | { kind: "rejected"; reason: string };
