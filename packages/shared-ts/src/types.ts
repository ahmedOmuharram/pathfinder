/**
 * Shared TypeScript types for Pathfinder - VEuPathDB Strategy Builder.
 *
 * Generated API types come from Kubb (packages/shared-ts/src/generated/).
 * Hand-written types below cover domain concepts that don't live in OpenAPI
 * (combine-operator enum, VEuPathDB site catalog, StrategyAst).
 */

import type {
  AuthStatusResponse,
  BackgroundTaskStarted,
  BootstrapResultResponse,
  CheckpointEvent,
  ColocationParams,
  ConfidenceIntervalResponse,
  ConfusionMatrixResponse,
  ControlSetResponse,
  ControlSetSummaryResponse,
  CreateConversationRequest,
  CrossValidationResultResponse,
  CustomEvent,
  DoneEvent,
  EnrichmentResultResponse,
  EnrichmentTermResponse,
  ErrorEvent,
  ExperimentConfigResponse,
  ExperimentMetricsResponse,
  ExperimentProgressDataResponse,
  ExperimentResponse,
  ExperimentSummaryResponse,
  FoldMetricsResponse,
  GeneConfidenceScoreResponse,
  GeneInfoResponse,
  GeneResolveResponse,
  GeneSearchResponse,
  GeneSearchResultResponse,
  GeneSet as GeneSetStreamPart,
  GeneSetResponse,
  GraphCleared,
  GraphPlan,
  GraphSnapshot,
  InterruptsEvent,
  MessagesCompleteEvent,
  MessagesPartialEvent,
  MemoryEditRequest,
  MemoryItem,
  MemoryListResponse,
  MemorySearchResponse,
  MemoryValue,
  ModelCatalogEntryResponse,
  NegativeSetVariantResponse,
  OpenConversationRequest,
  OpenConversationResponse,
  OperatorComparisonResponse,
  OperatorKnobResponse,
  OperatorVariantResponse,
  OptimizationParameterSpecData,
  OptimizationProgressEventData,
  OptimizationResultResponse,
  OptimizationSnapshot,
  OptimizationSpecResponse,
  OptimizationTrialData,
  ParamSpecResponse,
  PrivacySettings,
  PrivacyUpdate,
  ParameterSensitivityResponse,
  ParameterSweepPointResponse,
  VariantComparison,
  ScoredComparison,
  RankMetricsResponse,
  RecordTypeResponse,
  ResolvedGeneResponse,
  SearchResponse,
  StepAnalysisProgressDataResponse,
  StepAnalysisResultResponse,
  StepContributionResponse,
  StepCountsResponse,
  StepEvaluationResponse,
  StepResponse,
  LeadUsagePayload,
  StrategyLink,
  StrategyMeta,
  SubAgentCallPayload,
  SubAgentStepPayload,
  TurnStatusPayload,
  TurnStoppedPayload,
  TurnFailedPayload,
  ConversationTitlePayload,
  ConversationResponse,
  EnrichmentResultsChunk,
  TaskCompleted,
  TaskListItem,
  TaskListResponse,
  TaskProgress as TaskProgressStreamPart,
  TaskProgressEvent,
  TaskStatusResponse,
  ThresholdKnobResponse,
  ToolCallDelta,
  TreeOptimizationResultResponse,
  TreeOptimizationTrialResponse,
  TrialProgressDataResponse,
  TurnUsage,
  UpdatesEvent,
  UpdateConversationRequest,
  WDKVocabTerm,
  WDKTreeBoxVocabNode,
  WDKFilterOntologyTerm,
  WDKDatasetParser,
} from "./generated/types/index";

/**
 * Discriminated union of every backend SSE chat event. Wire shape is locked
 * by `packages/shared-py/src/shared_py/stream_events.py`. Frontend uses this
 * to type the `parseSseStream` async iterator.
 */
export type StreamEvent =
  | (MessagesPartialEvent & { type: "messages/partial" })
  | (MessagesCompleteEvent & { type: "messages/complete" })
  | (UpdatesEvent & { type: "updates" })
  | (CustomEvent & { type: "custom" })
  | (InterruptsEvent & { type: "interrupts" })
  | (CheckpointEvent & { type: "checkpoint" })
  | (ErrorEvent & { type: "error" })
  | (DoneEvent & { type: "done" });

export type StreamEventType = StreamEvent["type"];

export type { MessagesPartialEvent, MessagesCompleteEvent, ToolCallDelta };

export type ModelCatalogEntry = ModelCatalogEntryResponse;
export type GeneSearchResult = GeneSearchResultResponse;
export type { GeneSearchResponse, GeneResolveResponse };
export type ResolvedGene = ResolvedGeneResponse;
export type Search = SearchResponse;
export type RecordType = RecordTypeResponse;
export type {
  ConversationResponse,
  CreateConversationRequest,
  OpenConversationRequest,
  OpenConversationResponse,
  StepCountsResponse,
  UpdateConversationRequest,
};
export type ParamSpec = ParamSpecResponse;
export type {
  WDKVocabTerm,
  WDKTreeBoxVocabNode,
  WDKFilterOntologyTerm,
  WDKDatasetParser,
};

export interface SearchValidationErrors {
  general?: string[];
  byKey?: Record<string, string[]>;
}
export interface SearchValidationPayload {
  isValid: boolean;
  normalizedContextValues?: Record<string, unknown>;
  errors?: SearchValidationErrors;
}
export interface SearchValidationResponse {
  validation: SearchValidationPayload;
}

export type OptimizationProgressData = OptimizationProgressEventData;
export type { OptimizationTrialData };
export type OptimizationParameterSpec = OptimizationParameterSpecData;

export type ConfusionMatrix = ConfusionMatrixResponse;
export type ExperimentMetrics = ExperimentMetricsResponse;
export type GeneInfo = GeneInfoResponse;
export type FoldMetrics = FoldMetricsResponse;
export type CrossValidationResult = CrossValidationResultResponse;
export type EnrichmentTerm = EnrichmentTermResponse;
export type EnrichmentResult = EnrichmentResultResponse;
export type BootstrapResult = BootstrapResultResponse;
export type ConfidenceInterval = ConfidenceIntervalResponse;
export type RankMetrics = RankMetricsResponse;
export type NegativeSetVariant = NegativeSetVariantResponse;
export type StepEvaluation = StepEvaluationResponse;
export type OperatorVariant = OperatorVariantResponse;
export type OperatorComparison = OperatorComparisonResponse;
export type StepContribution = StepContributionResponse;
export type ParameterSweepPoint = ParameterSweepPointResponse;
export type ParameterSensitivity = ParameterSensitivityResponse;
export type StepAnalysisResult = StepAnalysisResultResponse;
export type TreeOptimizationTrial = TreeOptimizationTrialResponse;
export type TreeOptimizationResult = TreeOptimizationResultResponse;
export type ExperimentConfig = ExperimentConfigResponse;
export type Experiment = ExperimentResponse;
export type ExperimentSummary = ExperimentSummaryResponse;
export type OptimizeSpec = OptimizationSpecResponse;
export type ThresholdKnob = ThresholdKnobResponse;
export type OperatorKnob = OperatorKnobResponse;

export type { ColocationParams };
export type ControlSetSummary = ControlSetSummaryResponse;
export type OptimizationResult = OptimizationResultResponse;
export type TrialProgressData = TrialProgressDataResponse;
export type StepAnalysisProgressData = StepAnalysisProgressDataResponse;
export type ExperimentProgressData = ExperimentProgressDataResponse;

export type Step = StepResponse;
export type GeneSet = GeneSetResponse;
export type GeneConfidenceScore = GeneConfidenceScoreResponse;
export type ControlSet = ControlSetResponse;

export type Strategy = Omit<ConversationResponse, "steps" | "isSaved"> & {
  steps: StepResponse[];
  isSaved: boolean;
  activePlan?: Record<string, unknown> | null;
};

export type { AuthStatusResponse };

export const CombineOperator = {
  INTERSECT: "INTERSECT",
  MINUS: "MINUS",
  RMINUS: "RMINUS",
  LONLY: "LONLY",
  RONLY: "RONLY",
  COLOCATE: "COLOCATE",
  UNION: "UNION",
} as const;

export type CombineOperator =
  (typeof CombineOperator)[keyof typeof CombineOperator];

export const CombineOperatorLabels: Record<CombineOperator, string> = {
  INTERSECT: "IDs in common (AND)",
  MINUS: "In left, not in right",
  RMINUS: "In right, not in left",
  LONLY: "Left only",
  RONLY: "Right only",
  COLOCATE: "Genomic colocation",
  UNION: "Combined (OR)",
};

export const CombineOperatorBadgeLabels: Record<CombineOperator, string> = {
  INTERSECT: "AND (INTERSECT)",
  MINUS: "NOT (MINUS LEFT)",
  RMINUS: "NOT (MINUS RIGHT)",
  LONLY: "LEFT ONLY",
  RONLY: "RIGHT ONLY",
  COLOCATE: "NEAR (COLOCATE)",
  UNION: "OR (UNION)",
};

export interface StepFilter {
  name: string;
  value?: unknown;
  disabled: boolean;
}

export interface StepAnalysis {
  analysisType: string;
  parameters?: Record<string, unknown>;
  customName?: string | null;
}

export interface StepReport {
  reportName?: string;
  config?: Record<string, unknown>;
}

/**
 * Strategy AST — the built/executed strategy's step tree (NOT the planning
 * artifact from the planning agent; see `PlanArtifact` for that).
 */
export interface BaseStrategyNode {
  id?: string;
  displayName?: string;
  filters?: StepFilter[];
  analyses?: StepAnalysis[];
  reports?: StepReport[];
}

export interface StrategyStepNode extends BaseStrategyNode {
  searchName: string;
  parameters?: NonNullable<StepResponse["parameters"]>;
  primaryInput?: StrategyStepNode;
  secondaryInput?: StrategyStepNode;
  operator?: CombineOperator;
  colocationParams?: ColocationParams;
  wdkWeight?: number | null;
}

export interface StrategyAst {
  recordType: string;
  root: StrategyStepNode;
  name?: string | null;
  description?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface VEuPathDBSite {
  id: string;
  name: string;
  displayName: string;
  baseUrl: string;
  projectId: string;
  isPortal: boolean;
}

export function siteDisplayName(siteId: string): string {
  const site = VEUPATHDB_SITES.find((s) => s.id === siteId);
  return site?.displayName ?? site?.name ?? siteId;
}

/** The site's brand name, for a label with no room for the long form. */
export function siteShortName(siteId: string): string {
  const site = VEUPATHDB_SITES.find((s) => s.id === siteId);
  return site?.name ?? siteId;
}

export const VEUPATHDB_SITES: VEuPathDBSite[] = [
  { id: "veupathdb", name: "VEuPathDB", displayName: "VEuPathDB Portal (All organisms)", baseUrl: "https://veupathdb.org", projectId: "EuPathDB", isPortal: true },
  { id: "plasmodb", name: "PlasmoDB", displayName: "PlasmoDB (Plasmodium)", baseUrl: "https://plasmodb.org", projectId: "PlasmoDB", isPortal: false },
  { id: "toxodb", name: "ToxoDB", displayName: "ToxoDB (Toxoplasma)", baseUrl: "https://toxodb.org", projectId: "ToxoDB", isPortal: false },
  { id: "cryptodb", name: "CryptoDB", displayName: "CryptoDB (Cryptosporidium)", baseUrl: "https://cryptodb.org", projectId: "CryptoDB", isPortal: false },
  { id: "giardiadb", name: "GiardiaDB", displayName: "GiardiaDB (Giardia)", baseUrl: "https://giardiadb.org", projectId: "GiardiaDB", isPortal: false },
  { id: "amoebadb", name: "AmoebaDB", displayName: "AmoebaDB (Amoeba)", baseUrl: "https://amoebadb.org", projectId: "AmoebaDB", isPortal: false },
  { id: "microsporidiadb", name: "MicrosporidiaDB", displayName: "MicrosporidiaDB (Microsporidia)", baseUrl: "https://microsporidiadb.org", projectId: "MicrosporidiaDB", isPortal: false },
  { id: "piroplasmadb", name: "PiroplasmaDB", displayName: "PiroplasmaDB (Piroplasma)", baseUrl: "https://piroplasmadb.org", projectId: "PiroplasmaDB", isPortal: false },
  { id: "tritrypdb", name: "TriTrypDB", displayName: "TriTrypDB (Kinetoplastids)", baseUrl: "https://tritrypdb.org", projectId: "TriTrypDB", isPortal: false },
  { id: "trichdb", name: "TrichDB", displayName: "TrichDB (Trichomonas)", baseUrl: "https://trichdb.org", projectId: "TrichDB", isPortal: false },
  { id: "fungidb", name: "FungiDB", displayName: "FungiDB (Fungi)", baseUrl: "https://fungidb.org", projectId: "FungiDB", isPortal: false },
  { id: "hostdb", name: "HostDB", displayName: "HostDB (Hosts)", baseUrl: "https://hostdb.org", projectId: "HostDB", isPortal: false },
  { id: "vectorbase", name: "VectorBase", displayName: "VectorBase (Vectors)", baseUrl: "https://vectorbase.org", projectId: "VectorBase", isPortal: false },
  { id: "orthomcl", name: "OrthoMCL", displayName: "OrthoMCL (Orthologs)", baseUrl: "https://orthomcl.org", projectId: "OrthoMCL", isPortal: false },
];

export type ModelProvider = "openai" | "anthropic" | "google" | "ollama" | "mock";
export type ReasoningEffort = "none" | "low" | "medium" | "high";

export type PipelinePhase = "frame" | "build" | "execution" | "verification";

export type PhaseStatus =
  | "started"
  | "completed"
  | "failed"
  | "awaiting_approval"
  | "awaiting_input";

export type StepKind = "search" | "transform" | "combine";

export interface OptimizationTrial {
  trialNumber: number;
  parameters?: Record<string, unknown>;
  score: number;
  recall?: number | null;
  falsePositiveRate?: number | null;
  estimatedSize?: number | null;
  positiveHits?: number | null;
  negativeHits?: number | null;
  totalPositives?: number | null;
  totalNegatives?: number | null;
}

export type OptimizationStatus =
  | "started"
  | "running"
  | "completed"
  | "cancelled"
  | "error";

export type Classification = "TP" | "FP" | "FN" | "TN";

export type ExperimentMode = "single" | "multi-step" | "import";

export type EnrichmentAnalysisType =
  | "go_function"
  | "go_component"
  | "go_process"
  | "pathway"
  | "word";

export type ExperimentStatus =
  | "pending"
  | "running"
  | "completed"
  | "error"
  | "cancelled";

export type StepContributionVerdict = "essential" | "helpful" | "neutral" | "harmful";

export type MemoryKind = MemoryValue["kind"];
export type { MemoryValue, MemoryItem, MemoryListResponse, MemorySearchResponse, MemoryEditRequest };

export type { PrivacySettings, PrivacyUpdate };

export type { TaskListItem, TaskListResponse, TaskProgressEvent, TaskStatusResponse };

export type {
  GraphSnapshot,
  GraphPlan,
  GraphCleared,
  StrategyMeta,
  StrategyLink,
  VariantComparison,
  ScoredComparison,
  OptimizationSnapshot,
  BackgroundTaskStarted,
  TaskCompleted,
  TurnUsage,
  EnrichmentResultsChunk,
};
export type GeneSetPart = GeneSetStreamPart;
export type TaskProgressChunk = TaskProgressStreamPart;

// ── Data-part kind → payload mapping ────────────────────────────────────
// Used by the frontend content-part dispatcher (ts-pattern exhaustive match).
// Adding a backend kind here WITHOUT adding a renderer triggers a compile error.

export type DataConversationTitlePayload = ConversationTitlePayload;

export type DataSubAgentCallPayload = SubAgentCallPayload;
export type DataSubAgentStepPayload = SubAgentStepPayload;
export type DataLeadUsagePayload = LeadUsagePayload;

export interface LedgerIntentPayload {
  classification: string;
  inferredGoal: string;
  isDifferential: boolean;
  differentialSides: string[];
}

export interface LedgerCriterionPayload {
  id: string;
  text: string;
  searchName: string;
  role: string;
  resolvedParams: Record<string, unknown>;
  /** Params holding the search's own default rather than a value the request
   * stated. A default is a safe choice and a silent one. */
  defaultedParams?: string[];
  openParams: { criterionId: string; paramName: string; question: string }[];
  confidence: number;
}

export interface LedgerSpecPayload {
  goal: string;
  interpretedGoal: string;
  recordType: string;
  organismScope: string | null;
  title: string;
  criteria: LedgerCriterionPayload[];
  dropped: { text: string; reason: string }[];
  openSlots: { criterionId: string; paramName: string; question: string }[];
  readyToBuild: boolean;
}

/** Which way a differential criterion points. WDK computes fold change as
 * comparator-vs-reference, so swapping the two inverts the biology while still
 * returning a full, plausible gene set — a failure with nothing to notice
 * unless the direction is shown. */
export interface LedgerContrastPayload {
  criterionId: string;
  comparator?: string | null;
  reference?: string | null;
  direction?: string | null;
  /** Stated the way a biologist would: "up-regulated in female vs male". */
  summary: string;
}

export interface LedgerFramePayload {
  present: boolean;
  criteriaCount: number;
  boundCount: number;
  openSlotCount: number;
  droppedCount: number;
  readyToBuild: boolean;
  needsUser: boolean;
  spec: LedgerSpecPayload | null;
  /** One entry per criterion that contrasts two sample groups. */
  contrasts: LedgerContrastPayload[];
  /** Compact combine-tree string, e.g. "(GenesByText INTERSECT GenesByTaxon)".
   * Absent (exclude_none) until a structure is set. */
  structureRender?: string | null;
}

export interface LedgerNodeResultPayload {
  nodeId: string;
  searchName: string;
  wdkStepId?: number | null;
  count?: number | null;
  status: "ok" | "zero" | "failed";
  error?: string | null;
}

export interface LedgerBuildPayload {
  pushedCount: number;
  failedCount: number;
  skippedCount: number;
  zeroResultSteps: string[];
  needsRecovery: boolean;
  recoveryKind:
    | "none"
    | "transient_retry"
    | "param_replan"
    | "search_replan"
    | "user_clarify"
    | "empty_result_review";
  succeeded: boolean;
  /** Per-node build detail: which search returned how many genes, plus failures.
   * Optional: absent on ledger snapshots persisted before this field existed. */
  nodeResults?: LedgerNodeResultPayload[];
  wdkStrategyId?: number | null;
  wdkUrl?: string | null;
}

export interface LedgerVerificationDigestPayload {
  prose: string;
  reason: string;
  success: boolean;
  keyFindings: string[];
  caveats: string[];
}

export interface LedgerVerificationPayload {
  complete: boolean;
  successful: boolean;
  /** Full verification digest — absent (exclude_none) until verification runs. */
  digest?: LedgerVerificationDigestPayload | null;
}

export interface LedgerConstraintPayload {
  constraint: {
    kind: string;
    requestedValue: string;
    label: string;
    source: "user_explicit" | "assumed";
    hard: boolean;
  };
  status: "provisional" | "grounded" | "substituted" | "ungroundable";
  realizedValue?: string | null;
  note: string;
}

export interface LedgerConstraintsPayload {
  grounded: LedgerConstraintPayload[];
  unmetCount: number;
  blocking: boolean;
}

export interface DataLedgerUpdatePayload {
  userIntent: LedgerIntentPayload | null;
  frame: LedgerFramePayload;
  build: LedgerBuildPayload;
  verification: LedgerVerificationPayload;
  constraints: LedgerConstraintsPayload;
  subAgentCallsThisTurn: number;
  subAgentCallsTotal: number;
}

export interface DataMemoryRetrievedPayload {
  memories: Array<{
    key: string;
    kind: string;
    name: string;
    summary: string;
    score: number;
  }>;
}

export interface DataVerificationSummaryPayload {
  passed: boolean;
  checks: Array<{
    name: string;
    passed: boolean;
    detail?: string;
  }>;
  summary: string;
}

export type KnownDataPartKind =
  | "data-sub-agent-call"
  | "data-sub-agent-step"
  | "data-ledger-update"
  | "data-background-task-started"
  | "data-task-progress"
  | "data-task-completed"
  | "data-enrichment-results"
  | "data-strategy-link"
  | "data-strategy-meta"
  | "data-graph-snapshot"
  | "data-graph-cleared"
  | "data-variant-comparison"
  | "data-scored-comparison"
  | "data-memory-retrieved"
  | "data-gene-set"
  | "data-verification-summary"
  | "data-conversation-title"
  | "data-scratchpad-updated"
  | "data-turn-usage"
  | "data-turn-status"
  | "data-turn-stopped"
  | "data-turn-failed"
  | "data-lead-usage";

/**
 * Kinds this app renders, plus whatever another assistant registers. An
 * unknown kind type-checks here and reaches the fallback renderer at runtime.
 */
export type DataPartKind = KnownDataPartKind | (string & {});

export interface DataPartPayloadMap {
  "data-sub-agent-call": DataSubAgentCallPayload;
  "data-sub-agent-step": DataSubAgentStepPayload;
  "data-ledger-update": DataLedgerUpdatePayload;
  "data-background-task-started": BackgroundTaskStarted;
  "data-task-progress": TaskProgressStreamPart;
  "data-task-completed": TaskCompleted;
  "data-enrichment-results": EnrichmentResultsChunk;
  "data-strategy-link": StrategyLink;
  "data-strategy-meta": StrategyMeta;
  "data-graph-snapshot": GraphSnapshot;
  "data-graph-cleared": GraphCleared;
  "data-variant-comparison": VariantComparison;
  "data-scored-comparison": ScoredComparison;
  "data-memory-retrieved": DataMemoryRetrievedPayload;
  "data-gene-set": GeneSetStreamPart;
  "data-verification-summary": DataVerificationSummaryPayload;
  "data-conversation-title": DataConversationTitlePayload;
  "data-scratchpad-updated": Record<string, never>;
  "data-turn-usage": TurnUsage;
  "data-turn-status": TurnStatusPayload;
  "data-turn-stopped": TurnStoppedPayload;
  "data-turn-failed": TurnFailedPayload;
  "data-lead-usage": DataLeadUsagePayload;
}

export type TypedDataPart<K extends DataPartKind = DataPartKind> = {
  kind: K;
  data: K extends KnownDataPartKind ? DataPartPayloadMap[K] : unknown;
};

export type AnyTypedDataPart = {
  [K in KnownDataPartKind]: TypedDataPart<K>;
}[KnownDataPartKind];
