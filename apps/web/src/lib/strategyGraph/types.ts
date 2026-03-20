/**
 * WDK step parameters are inherently dynamic -- each search has a different
 * set of parameters.  `Step.parameters` in `@pathfinder/shared` is typed as
 * `Record<string, unknown>` for this reason.  We re-export the alias here so
 * consumers in the graph/editor layers can reference it consistently.
 */
export type StepParameters = Record<string, unknown>;

export interface GraphSnapshotStepInput {
  id: string;
  kind?: string;
  displayName?: string;
  searchName?: string;
  operator?: string;
  parameters?: StepParameters;
  inputStepIds?: string[];
  primaryInputStepId?: string;
  secondaryInputStepId?: string;
  recordType?: string;
}

export interface GraphSnapshotInput {
  graphId?: string;
  graphName?: string;
  recordType?: string | null;
  name?: string;
  description?: string | null;
  rootStepId?: string | null;
  steps?: GraphSnapshotStepInput[];
}
