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
  ClarificationQuestion,
  ColocationParams,
  ConfidenceIntervalResponse,
  ConfusionMatrixResponse,
  ControlSetResponse,
  ControlSetSummaryResponse,
  CreateConversationRequest,
  CrossValidationResultResponse,
  CustomEvent,
  DecisionPresented,
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
  ParameterSensitivityResponse,
  ParameterSweepPointResponse,
  PhaseChange,
  PlanArtifact,
  PlanUpdate,
  PushConversationRequest,
  ProblemFrame,
  RankMetricsResponse,
  RecordTypeResponse,
  ResearchNote,
  ResolvedGeneResponse,
  SearchResponse,
  StepAnalysisProgressDataResponse,
  StepAnalysisResultResponse,
  StepContributionResponse,
  StepCountsResponse,
  StepEvaluationResponse,
  StepResponse,
  StrategyLink,
  StrategyMeta,
  StrategyPatch,
  ConversationResponse,
  TaskCompleted,
  TaskProgress as TaskProgressStreamPart,
  TaskProgressEvent,
  TaskStatusResponse,
  ThresholdKnobResponse,
  ToolCallDelta,
  TreeOptimizationResultResponse,
  TreeOptimizationTrialResponse,
  TrialProgressDataResponse,
  UpdatesEvent,
  UpdateConversationRequest,
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
  PushConversationRequest,
  StepCountsResponse,
  UpdateConversationRequest,
};
export type ParamSpec = ParamSpecResponse;

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
  parameters?: Record<string, unknown>;
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

export interface PipelinePhaseConfig {
  modelId: string;
  reasoningEffort: ReasoningEffort;
}

export interface PipelineConfig {
  scoping: PipelinePhaseConfig;
  discovery: PipelinePhaseConfig;
  planning: PipelinePhaseConfig;
  execution: PipelinePhaseConfig;
  verification: PipelinePhaseConfig;
}

export type TierName = "quality" | "balanced" | "fast" | "custom";

export type PipelinePhase =
  | "scoping"
  | "discovery"
  | "planning"
  | "execution"
  | "verification";

export type PhaseStatus =
  | "started"
  | "completed"
  | "failed"
  | "awaiting_approval"
  | "awaiting_input";

export type { ClarificationQuestion, ResearchNote };

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

export type { TaskProgressEvent, TaskStatusResponse };

export type {
  GraphSnapshot,
  GraphPlan,
  GraphCleared,
  StrategyPatch,
  StrategyMeta,
  StrategyLink,
  PlanArtifact,
  PlanUpdate,
  DecisionPresented,
  OptimizationSnapshot,
  PhaseChange,
  BackgroundTaskStarted,
  TaskCompleted,
};
export type ProblemFramePart = ProblemFrame;
export type GeneSetPart = GeneSetStreamPart;
export type TaskProgressChunk = TaskProgressStreamPart;

// ── Data-part kind → payload mapping ────────────────────────────────────
// Used by the frontend content-part dispatcher (ts-pattern exhaustive match).
// Adding a backend kind here WITHOUT adding a renderer triggers a compile error.

export interface DataPhaseStartPayload {
  phase: string;
  traceId: string;
  model: string;
}

export interface DataConversationTitlePayload {
  title: string;
}

export interface DataTurnRejectedPayload {
  message: string;
  reason: string;
}

export interface DataTurnQaPayload {
  answer: string;
  reason: string;
}

export interface DataSupervisorDecisionPayload {
  to: string;
  reason: string;
}

export interface DataToolApprovalRequestPayload {
  toolCallId: string;
  toolName: string;
  args: Record<string, unknown>;
}

export interface DataToolApprovalResultPayload {
  toolCallId: string;
  approved: boolean;
  reason?: string;
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

export type DataPartKind =
  | "data-phase-start"
  | "data-phase-change"
  | "data-background-task-started"
  | "data-task-progress"
  | "data-task-completed"
  | "data-strategy-link"
  | "data-problem-frame"
  | "data-plan-artifact"
  | "data-tool-approval-request"
  | "data-tool-approval-result"
  | "data-memory-retrieved"
  | "data-gene-set-created"
  | "data-verification-summary"
  | "data-conversation-title"
  | "data-turn-rejected"
  | "data-turn-qa"
  | "data-supervisor-decision";

export interface DataPartPayloadMap {
  "data-phase-start": DataPhaseStartPayload;
  "data-phase-change": PhaseChange;
  "data-background-task-started": BackgroundTaskStarted;
  "data-task-progress": TaskProgressStreamPart;
  "data-task-completed": TaskCompleted;
  "data-strategy-link": StrategyLink;
  "data-problem-frame": ProblemFrame;
  "data-plan-artifact": PlanArtifact;
  "data-tool-approval-request": DataToolApprovalRequestPayload;
  "data-tool-approval-result": DataToolApprovalResultPayload;
  "data-memory-retrieved": DataMemoryRetrievedPayload;
  "data-gene-set-created": GeneSetStreamPart;
  "data-verification-summary": DataVerificationSummaryPayload;
  "data-conversation-title": DataConversationTitlePayload;
  "data-turn-rejected": DataTurnRejectedPayload;
  "data-turn-qa": DataTurnQaPayload;
  "data-supervisor-decision": DataSupervisorDecisionPayload;
}

export type TypedDataPart<K extends DataPartKind = DataPartKind> = {
  kind: K;
  data: DataPartPayloadMap[K];
};

export type AnyTypedDataPart = {
  [K in DataPartKind]: TypedDataPart<K>;
}[DataPartKind];
