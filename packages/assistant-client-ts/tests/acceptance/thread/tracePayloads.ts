/**
 * The recorded EDA payloads and ids of the frozen turn.
 * Frozen with the buildTrace acceptance modules: implementers may not touch tests/acceptance/**.
 */
export const MESSAGE_ID = "11111111-1111-1111-1111-111111111111";
export const TASK_ID = "00000000-0000-0000-0000-0000000000aa";
export const DATASET = "DS_e973eadd57";
export const SAMPLE = {
  entityId: "ENT_8151325d",
  entityDisplayName: "Sample",
  count: 6,
  unfilteredCount: 12,
};
export const READS = {
  entityId: "ENT_fd574cd6",
  entityDisplayName: "pfal3D7 htseq counts",
  count: 34320,
  unfilteredCount: 68640,
};

export const ANALYSIS_STATE = {
  siteId: "plasmodb",
  datasetId: DATASET,
  studyId: "STUDY_e973eadd57",
  analysisId: "a-1",
  revision: 3,
  numFilters: 2,
  numComputations: 1,
  canExportRows: true,
  studyDisplayName: "Heat shock response in sensitive mutants (LRR5, DHC)",
  displayName: "Febrile samples",
  filters: [
    {
      entityId: "ENT_8151325d",
      variableId: "VAR_081ab087",
      type: "stringSet",
      stringSet: ["febrile"],
    },
    {
      entityId: "ENT_8151325d",
      variableId: "VAR_7033e90f",
      type: "numberRange",
      min: 37,
      max: 42,
    },
  ],
  filterSummaries: ["temperature_condition is febrile", "Temperature is 37 to 42"],
  entityCounts: [SAMPLE, READS],
};

export const SUBSET_PREVIEW = {
  datasetId: DATASET,
  analysisId: "a-1",
  entityCounts: [SAMPLE],
  distributionNote: null,
  distribution: {
    variableId: "VAR_7033e90f",
    variableDisplayName: "Temperature",
    labels: ["[37, 38)", "[41, 42]"],
    values: [6, 6],
    subsetSize: 6,
    numVarValues: 6,
    numMissingCases: 0,
    isMultiValued: false,
  },
};

export const VOLCANO = {
  datasetId: DATASET,
  analysisId: "a-1",
  chart: "volcano",
  effectSizeLabel: "log2(Fold Change)",
  effectSizeThreshold: 1,
  significanceThreshold: 0.05,
  effectDirection: "upAndDown",
  totalPoints: 5511,
  retainedPoints: 1543,
  points: [
    {
      pointId: "PF3D7_0100100",
      effectSize: -0.218035922112735,
      pValue: 0.350285751849808,
      adjustedPValue: 0.46960449943855,
      retained: false,
    },
    {
      pointId: "PF3D7_0100200",
      effectSize: 3.94437533216012,
      pValue: 1.95781599815607e-5,
      adjustedPValue: 0.000137772236907279,
      retained: true,
    },
    {
      pointId: "PF3D7_MIT04200",
      effectSize: -1.49447459261845,
      pValue: null,
      adjustedPValue: null,
      retained: false,
    },
  ],
};

export const SUB_AGENT = {
  toolCallId: "sa_1",
  subAgent: "frame_problem",
  phase: "frame",
  modelId: "openai:gpt-5.6-luna",
  summary: "frame the heat shock question",
};
