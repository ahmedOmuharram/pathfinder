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
