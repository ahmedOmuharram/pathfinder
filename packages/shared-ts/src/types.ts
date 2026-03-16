/**
 * Shared TypeScript types for Pathfinder - VEuPathDB Strategy Builder
 *
 * Canonical combine operators (matches WDK BooleanOperator): INTERSECT, MINUS,
 * RMINUS, LONLY, RONLY, COLOCATE, UNION.
 */

import type { components } from "./openapi.generated";

// ── Generated API types (SSOT — do not hand-edit these shapes) ─────────────
// Re-exported from openapi.generated.ts with aliases matching existing names.
// Types where the generated shape is structurally compatible with existing usage.

export type TokenUsage = components["schemas"]["TokenUsageResponse"];
export type ModelCatalogEntry = components["schemas"]["ModelCatalogEntryResponse"];
export type GeneSearchResult = components["schemas"]["GeneSearchResultResponse"];
export type GeneSearchResponse = components["schemas"]["GeneSearchResponse"];
export type ResolvedGene = components["schemas"]["ResolvedGeneResponse"];
export type GeneResolveResponse = components["schemas"]["GeneResolveResponse"];
export type Search = components["schemas"]["SearchResponse"];
export type RecordType = components["schemas"]["RecordTypeResponse"];
export type StepCountsResponse = components["schemas"]["StepCountsResponse"];
export type OpenStrategyRequest = components["schemas"]["OpenStrategyRequest"];
export type OpenStrategyResponse = components["schemas"]["OpenStrategyResponse"];
export type ChatMention = components["schemas"]["ChatMention"];
export type ChatRequest = components["schemas"]["ChatRequest"];
export type ParamSpec = components["schemas"]["ParamSpecResponse"];
export type SearchValidationErrors = components["schemas"]["SearchValidationErrors"];
export type SearchValidationPayload = components["schemas"]["SearchValidationPayload"];
export type SearchValidationResponse = components["schemas"]["SearchValidationResponse"];
export type CreateStrategyRequest = components["schemas"]["CreateStrategyRequest"];
export type UpdateStrategyRequest = components["schemas"]["UpdateStrategyRequest"];

// SSE event data types (generated SSOT)
export type MessageStartData = components["schemas"]["MessageStartEventData"];
export type UserMessageData = components["schemas"]["UserMessageEventData"];
export type AssistantDeltaData = components["schemas"]["AssistantDeltaEventData"];
export type AssistantMessageData = components["schemas"]["AssistantMessageEventData"];
export type TokenUsagePartialData = components["schemas"]["TokenUsagePartialEventData"];
export type SubKaniTaskStartData = components["schemas"]["SubKaniTaskStartEventData"];
export type SubKaniTaskEndData = components["schemas"]["SubKaniTaskEndEventData"];
export type SubKaniToolCallStartData = components["schemas"]["SubKaniToolCallStartEventData"];
export type SubKaniToolCallEndData = components["schemas"]["SubKaniToolCallEndEventData"];
export type SSEToolCallStartData = components["schemas"]["ToolCallStartEventData"];
export type SSEToolCallEndData = components["schemas"]["ToolCallEndEventData"];
export type ModelSelectedData = components["schemas"]["ModelSelectedEventData"];
export type SSEErrorData = components["schemas"]["ErrorEventData"];
export type StrategyMetaData = components["schemas"]["StrategyMetaEventData"];
export type StrategyLinkData = components["schemas"]["StrategyLinkEventData"];
export type GraphClearedData = components["schemas"]["GraphClearedEventData"];
export type ReasoningData = components["schemas"]["ReasoningEventData"];
export type MessageEndData = components["schemas"]["MessageEndEventData"];

// SSE event data types that use JSONObject/JSONValue — re-exported but
// downstream consumers use `as` casts or runtime checks for type safety.
export type GraphSnapshotData = components["schemas"]["GraphSnapshotEventData"];
export type GraphPlanData = components["schemas"]["GraphPlanEventData"];
export type StrategyUpdateData = components["schemas"]["StrategyUpdateEventData"];
export type ExecutorBuildRequestData = components["schemas"]["ExecutorBuildRequestEventData"];
export type WorkbenchGeneSetData = components["schemas"]["WorkbenchGeneSetEventData"];
export type CitationsData = components["schemas"]["CitationsEventData"];
export type PlanningArtifactData = components["schemas"]["PlanningArtifactEventData"];

// Optimization SSE event types
export type OptimizationProgressData = components["schemas"]["OptimizationProgressEventData"];
export type OptimizationTrialData = components["schemas"]["OptimizationTrialData"];
export type OptimizationParameterSpecData = components["schemas"]["OptimizationParameterSpecData"];

// Experiment response types
export type ConfusionMatrix = components["schemas"]["ConfusionMatrixResponse"];
export type ExperimentMetrics = components["schemas"]["ExperimentMetricsResponse"];
export type GeneInfo = components["schemas"]["GeneInfoResponse"];
export type FoldMetrics = components["schemas"]["FoldMetricsResponse"];
export type CrossValidationResult = components["schemas"]["CrossValidationResultResponse"];
export type EnrichmentTerm = components["schemas"]["EnrichmentTermResponse"];
export type EnrichmentResult = components["schemas"]["EnrichmentResultResponse"];
export type BootstrapResult = components["schemas"]["BootstrapResultResponse"];
export type ConfidenceInterval = components["schemas"]["ConfidenceIntervalResponse"];
export type RankMetrics = components["schemas"]["RankMetricsResponse"];
export type NegativeSetVariant = components["schemas"]["NegativeSetVariantResponse"];
export type StepEvaluation = components["schemas"]["StepEvaluationResponse"];
export type OperatorVariant = components["schemas"]["OperatorVariantResponse"];
export type OperatorComparison = components["schemas"]["OperatorComparisonResponse"];
export type StepContribution = components["schemas"]["StepContributionResponse"];
export type ParameterSweepPoint = components["schemas"]["ParameterSweepPointResponse"];
export type ParameterSensitivity = components["schemas"]["ParameterSensitivityResponse"];
export type StepAnalysisResult = components["schemas"]["StepAnalysisResultResponse"];
export type TreeOptimizationTrial = components["schemas"]["TreeOptimizationTrialResponse"];
export type TreeOptimizationResult = components["schemas"]["TreeOptimizationResultResponse"];
export type ExperimentConfig = components["schemas"]["ExperimentConfigResponse"];
export type Experiment = components["schemas"]["ExperimentResponse"];
export type ExperimentSummary = components["schemas"]["ExperimentSummaryResponse"];
export type OptimizeSpec = components["schemas"]["OptimizationSpecResponse"];
export type ThresholdKnob = components["schemas"]["ThresholdKnobResponse"];
export type OperatorKnob = components["schemas"]["OperatorKnobResponse"];

// Newly typed models (were JSONObject before)
export type Citation = components["schemas"]["CitationResponse"];
export type PlanningArtifact = components["schemas"]["PlanningArtifactResponse"];
export type ColocationParams = components["schemas"]["ColocationParams"];
export type ControlSetSummary = components["schemas"]["ControlSetSummaryResponse"];
export type OptimizationResult = components["schemas"]["OptimizationResultResponse"];
export type TrialProgressData = components["schemas"]["TrialProgressDataResponse"];
export type StepAnalysisProgressData = components["schemas"]["StepAnalysisProgressDataResponse"];
export type ExperimentProgressData = components["schemas"]["ExperimentProgressDataResponse"];

// REST response types — formerly hand-written, now generated SSOT
export type ToolCall = components["schemas"]["ToolCallResponse"];
export type SubKaniTokenUsage = components["schemas"]["SubKaniTokenUsageResponse"];
export type SubKaniActivity = components["schemas"]["SubKaniActivityResponse"];
export type Thinking = components["schemas"]["ThinkingResponse"];
export type StepFilter = components["schemas"]["StepFilterResponse"];
export type StepAnalysis = components["schemas"]["StepAnalysisResponse"];
export type StepReport = components["schemas"]["StepReportResponse"];
export type Step = components["schemas"]["StepResponse"];
export type GeneSet = components["schemas"]["GeneSetResponse"];
export type ControlSet = components["schemas"]["ControlSetResponse"];
/**
 * Strategy normalizes the generated StrategyResponse: `steps` and `isSaved`
 * always have values at runtime (backend defaults), but OpenAPI marks them
 * optional. We make them required here to match actual API behavior.
 */
export type Strategy = Omit<
  components["schemas"]["StrategyResponse"],
  "steps" | "isSaved"
> & {
  steps: components["schemas"]["StepResponse"][];
  isSaved: boolean;
};

// ── Hand-written types (frontend-enriched, not yet in generated schema) ────
// These types extend/differ from their generated counterparts with frontend-
// specific fields or stricter typing.  They'll migrate to generated re-exports
// as the backend schema evolves to cover their full shape.

// Combine Operations

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

/** Short display labels for operator badges (e.g. "AND (INTERSECT)"). */
export const CombineOperatorBadgeLabels: Record<CombineOperator, string> = {
  INTERSECT: "AND (INTERSECT)",
  MINUS: "NOT (MINUS LEFT)",
  RMINUS: "NOT (MINUS RIGHT)",
  LONLY: "LEFT ONLY",
  RONLY: "RIGHT ONLY",
  COLOCATE: "NEAR (COLOCATE)",
  UNION: "OR (UNION)",
};

/**
 * Maps WDK bq_operator values to canonical CombineOperator.
 * WDK uses INTERSECT, UNION, MINUS, RMINUS, LMINUS, LONLY, RONLY.
 */
export const WDK_OPERATOR_TO_COMBINE: Record<string, CombineOperator> = {
  INTERSECT: CombineOperator.INTERSECT,
  UNION: CombineOperator.UNION,
  MINUS: CombineOperator.MINUS,
  LMINUS: CombineOperator.MINUS,
  RMINUS: CombineOperator.RMINUS,
  LONLY: CombineOperator.LONLY,
  RONLY: CombineOperator.RONLY,
};

export const CombineOperatorShortLabels: Record<CombineOperator, string> = {
  INTERSECT: "Intersect",
  MINUS: "Minus",
  RMINUS: "Minus",
  LONLY: "Left only",
  RONLY: "Right only",
  COLOCATE: "Colocate",
  UNION: "Union",
};

export const DEFAULT_COMBINE_OPERATOR: CombineOperator = "INTERSECT";

/** WDK-specific short labels when operator comes from bq_operator. */
export const WDK_OPERATOR_SHORT_LABELS: Record<string, string> = {
  ...CombineOperatorShortLabels,
  LMINUS: "Minus",
};

export function getOperatorDisplayLabel(wdkOperator: string | null | undefined): string {
  if (!wdkOperator) return "";
  const norm = String(wdkOperator).toUpperCase();
  return WDK_OPERATOR_SHORT_LABELS[norm] ?? norm;
}

export function wdkOperatorToCombine(wdkOperator: string | null | undefined): CombineOperator {
  if (!wdkOperator) return DEFAULT_COMBINE_OPERATOR;
  const norm = String(wdkOperator).toUpperCase();
  return WDK_OPERATOR_TO_COMBINE[norm] ?? DEFAULT_COMBINE_OPERATOR;
}

// Strategy Plan DSL (AST)

export interface BasePlanNode {
  id?: string;
  displayName?: string;
  filters?: StepFilter[];
  analyses?: StepAnalysis[];
  reports?: StepReport[];
}

/**
 * Untyped recursive plan node.
 *
 * A node's kind is inferred from structure:
 * - combine: primaryInput && secondaryInput
 * - transform: primaryInput && !secondaryInput
 * - search: !primaryInput && !secondaryInput
 *
 * All nodes use `searchName` to identify the underlying WDK question/search.
 */
export interface PlanStepNode extends BasePlanNode {
  searchName: string;
  parameters?: Record<string, unknown>;
  primaryInput?: PlanStepNode;
  secondaryInput?: PlanStepNode;
  operator?: CombineOperator;
  colocationParams?: ColocationParams;
}

export interface StrategyPlan {
  recordType: string;
  root: PlanStepNode;
  metadata?: {
    name?: string;
    description?: string;
    siteId?: string;
    createdAt?: string;
  };
}

// VEuPathDB Site Configuration

export interface VEuPathDBSite {
  id: string;
  name: string;
  displayName: string;
  baseUrl: string;
  projectId: string;
  isPortal: boolean;
}

export const VEUPATHDB_SITES: VEuPathDBSite[] = [
  {
    id: "veupathdb",
    name: "VEuPathDB",
    displayName: "VEuPathDB Portal (All organisms)",
    baseUrl: "https://veupathdb.org",
    projectId: "EuPathDB",
    isPortal: true,
  },
  {
    id: "plasmodb",
    name: "PlasmoDB",
    displayName: "PlasmoDB (Plasmodium)",
    baseUrl: "https://plasmodb.org",
    projectId: "PlasmoDB",
    isPortal: false,
  },
  {
    id: "toxodb",
    name: "ToxoDB",
    displayName: "ToxoDB (Toxoplasma)",
    baseUrl: "https://toxodb.org",
    projectId: "ToxoDB",
    isPortal: false,
  },
  {
    id: "cryptodb",
    name: "CryptoDB",
    displayName: "CryptoDB (Cryptosporidium)",
    baseUrl: "https://cryptodb.org",
    projectId: "CryptoDB",
    isPortal: false,
  },
  {
    id: "giardiadb",
    name: "GiardiaDB",
    displayName: "GiardiaDB (Giardia)",
    baseUrl: "https://giardiadb.org",
    projectId: "GiardiaDB",
    isPortal: false,
  },
  {
    id: "amoebadb",
    name: "AmoebaDB",
    displayName: "AmoebaDB (Amoeba)",
    baseUrl: "https://amoebadb.org",
    projectId: "AmoebaDB",
    isPortal: false,
  },
  {
    id: "microsporidiadb",
    name: "MicrosporidiaDB",
    displayName: "MicrosporidiaDB (Microsporidia)",
    baseUrl: "https://microsporidiadb.org",
    projectId: "MicrosporidiaDB",
    isPortal: false,
  },
  {
    id: "piroplasmadb",
    name: "PiroplasmaDB",
    displayName: "PiroplasmaDB (Piroplasma)",
    baseUrl: "https://piroplasmadb.org",
    projectId: "PiroplasmaDB",
    isPortal: false,
  },
  {
    id: "tritrypdb",
    name: "TriTrypDB",
    displayName: "TriTrypDB (Kinetoplastids)",
    baseUrl: "https://tritrypdb.org",
    projectId: "TriTrypDB",
    isPortal: false,
  },
  {
    id: "fungidb",
    name: "FungiDB",
    displayName: "FungiDB (Fungi)",
    baseUrl: "https://fungidb.org",
    projectId: "FungiDB",
    isPortal: false,
  },
  {
    id: "hostdb",
    name: "HostDB",
    displayName: "HostDB (Hosts)",
    baseUrl: "https://hostdb.org",
    projectId: "HostDB",
    isPortal: false,
  },
  {
    id: "vectorbase",
    name: "VectorBase",
    displayName: "VectorBase (Vectors)",
    baseUrl: "https://vectorbase.org",
    projectId: "VectorBase",
    isPortal: false,
  },
  {
    id: "orthomcl",
    name: "OrthoMCL",
    displayName: "OrthoMCL (Orthologs)",
    baseUrl: "https://orthomcl.org",
    projectId: "OrthoMCL",
    isPortal: false,
  },
];

// Chat Types

export type MessageRole = "user" | "assistant" | "system";

export type ModelProvider = "openai" | "anthropic" | "google" | "ollama" | "mock";
export type ReasoningEffort = "none" | "low" | "medium" | "high";

/** Model selection passed with each chat request. */
export interface ModelSelection {
  provider?: ModelProvider;
  model?: string;
  reasoningEffort?: ReasoningEffort;
  contextSize?: number;
  responseTokens?: number;
  reasoningBudget?: number;
}

/**
 * Message extends the generated MessageResponse with frontend-only fields
 * (mentions and reasoningEffort are set locally, not persisted by the backend).
 */
export type Message = components["schemas"]["MessageResponse"] & {
  reasoningEffort?: ReasoningEffort;
  mentions?: ChatMention[];
};

export interface Conversation {
  id: string;
  siteId: string;
  title?: string;
  messages: Message[];
  strategyId: string;
  createdAt: string;
  updatedAt: string;
}

export type StepKind = "search" | "transform" | "combine";

// Search parameter validation/specs (UI-facing)

export interface SearchDetailsResponse {
  searchData?: Record<string, unknown>;
  validation?: Record<string, unknown>;
  searchConfig?: Record<string, unknown>;
  parameters?: Record<string, unknown>[];
  paramMap?: Record<string, unknown>;
  question?: Record<string, unknown>;
  [key: string]: unknown;
}

export type DependentParamsResponse = Record<string, unknown>[];

export interface PushResult {
  wdkStrategyId: number;
  wdkUrl: string;
}


// Parameter Optimisation

export interface OptimizationTrial {
  trialNumber: number;
  parameters?: Record<string, unknown>;
  score: number;
  recall?: number | null;
  falsePositiveRate?: number | null;
  resultCount?: number | null;
  positiveHits?: number | null;
  negativeHits?: number | null;
  totalPositives?: number | null;
  totalNegatives?: number | null;
}

export interface OptimizationParameterSpec {
  name: string;
  type: "numeric" | "integer" | "categorical";
  minValue?: number | null;
  maxValue?: number | null;
  logScale?: boolean;
  choices?: string[] | null;
}

export type OptimizationStatus =
  | "started"
  | "running"
  | "completed"
  | "cancelled"
  | "error";

// SSE Event Types

export type SSEEventType =
  | "message_start"
  | "content_delta"
  | "tool_call_start"
  | "tool_call_delta"
  | "tool_call_end"
  | "message_end"
  | "error";

export interface SSEEvent {
  type: SSEEventType;
  data: unknown;
}

export interface ContentDeltaEvent {
  type: "content_delta";
  data: { delta: string };
}

export interface ToolCallStartEvent {
  type: "tool_call_start";
  data: { id: string; name: string };
}

export interface ToolCallEndEvent {
  type: "tool_call_end";
  data: { id: string; result: string };
}

// Result Types

export interface PreviewRequest {
  strategyId: string;
  stepId: string;
  limit?: number;
}

export interface PreviewResponse {
  totalCount: number;
  records: Record<string, unknown>[];
  columns: string[];
}

export interface DownloadRequest {
  strategyId: string;
  stepId: string;
  format: "csv" | "json" | "tab";
  attributes?: string[];
}

export interface DownloadResponse {
  downloadUrl: string;
  expiresAt: string;
}

// Experiment Lab Types

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

export type ExperimentProgressPhase =
  | "started"
  | "optimizing"
  | "evaluating"
  | "cross_validating"
  | "enriching"
  | "step_analysis"
  | "completed"
  | "error";

// Gene Set Types

export type GeneSetSource = "strategy" | "paste" | "upload" | "derived" | "saved";

// Rank-based evaluation types

export type ControlSetSource = "paper" | "curation" | "db_build" | "other";

export type StepContributionVerdict = "essential" | "helpful" | "neutral" | "harmful";

export type StepAnalysisPhase =
  | "step_evaluation"
  | "operator_comparison"
  | "contribution"
  | "sensitivity";


// Classification for control test results
export type Classification = "TP" | "FP" | "FN" | "TN";

// Chat @-Mention References

export type ChatMentionType = "strategy" | "experiment";
