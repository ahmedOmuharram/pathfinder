/**
 * Shared TypeScript types for Pathfinder - VEuPathDB Strategy Builder
 *
 * Canonical combine operators (matches WDK BooleanOperator): INTERSECT, MINUS,
 * RMINUS, LONLY, RONLY, COLOCATE, UNION.
 */

import type { UIMessage } from "ai";
import type { components } from "./openapi.generated";

// ── Generated API types (SSOT — do not hand-edit these shapes) ─────────────
// Re-exported from openapi.generated.ts with aliases matching existing names.
// Types where the generated shape is structurally compatible with existing usage.

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
export type ParamSpec = components["schemas"]["ParamSpecResponse"];
// Search validation types — defined locally (not in OpenAPI spec since
// validation is a WDK proxy endpoint, not a PathFinder model).
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

export type CreateStrategyRequest = components["schemas"]["CreateStrategyRequest"];
export type UpdateStrategyRequest = components["schemas"]["UpdateStrategyRequest"];

// Optimization event types (used by experiment/optimization streaming)
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
export type ColocationParams = components["schemas"]["ColocationParams"];
export type ControlSetSummary = components["schemas"]["ControlSetSummaryResponse"];
export type OptimizationResult = components["schemas"]["OptimizationResultResponse"];
export type TrialProgressData = components["schemas"]["TrialProgressDataResponse"];
export type StepAnalysisProgressData = components["schemas"]["StepAnalysisProgressDataResponse"];
export type ExperimentProgressData = components["schemas"]["ExperimentProgressDataResponse"];

// REST response types — formerly hand-written, now generated SSOT
export type Step = components["schemas"]["StepResponse"];
export type GeneSet = components["schemas"]["GeneSetResponse"];
export type GeneConfidenceScore =
  components["schemas"]["GeneConfidenceScoreResponse"];
export type ControlSet = components["schemas"]["ControlSetResponse"];
/**
 * Strategy normalizes the generated StrategyResponse: `steps` and `isSaved`
 * always have values at runtime (backend defaults), but OpenAPI marks them
 * optional. We make them required here to match actual API behavior.
 *
 * `activePlan` is served by the backend detail endpoint but not yet in the
 * OpenAPI spec — added here until the next spec regeneration.
 */
export type Strategy = Omit<
  components["schemas"]["StrategyResponse"],
  "steps" | "isSaved"
> & {
  steps: components["schemas"]["StepResponse"][];
  isSaved: boolean;
  activePlan?: Record<string, unknown> | null;
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


// Strategy Plan DSL (AST)

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
  wdkWeight?: number | null;
}

export interface StrategyPlan {
  recordType: string;
  root: PlanStepNode;
  name?: string | null;
  description?: string | null;
  metadata?: Record<string, unknown> | null;
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
    id: "trichdb",
    name: "TrichDB",
    displayName: "TrichDB (Trichomonas)",
    baseUrl: "https://trichdb.org",
    projectId: "TrichDB",
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

export interface ClarificationQuestion {
  question: string;
  context?: string;
  field?: string | null;
  priority?: "blocking" | "optional";
  options?: string[];
}

export interface ResearchNote {
  source: string;
  finding: string;
  url?: string | null;
  citationId?: string | null;
}

export interface ProblemFrame {
  [key: string]: unknown;
  userGoal: string;
  interpretedGoal: string;
  organismScope?: string | null;
  recordType?: string | null;
  biologicalEntities?: string[];
  inclusionCriteria?: string[];
  exclusionCriteria?: string[];
  likelyDataSources?: string[];
  successCriteria?: string[];
  assumptions?: string[];
  blockingQuestions?: ClarificationQuestion[];
  optionalQuestions?: ClarificationQuestion[];
  researchNotes?: ResearchNote[];
  readyForWdkDiscovery: boolean;
  confidence: number;
}

export type StepKind = "search" | "transform" | "combine";

// Parameter Optimisation

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

export type StepContributionVerdict = "essential" | "helpful" | "neutral" | "harmful";

// Classification for control test results
export type Classification = "TP" | "FP" | "FN" | "TN";

// ── Chat stream-part payloads (AI SDK v6 DataChunk data types) ─────────────
// Typed shapes for every `data-<name>` part emitted during a chat turn.
// One-to-one with the Pydantic models in `shared_py.stream_parts`.
//
// NOTE: `GeneSet` and `ProblemFrame` are already taken by existing types
// above (the workbench REST resource and the hand-written frontend shape,
// respectively), so the stream-part variants use the `Part` suffix to
// avoid collisions. The `PathfinderDataParts` map below references the
// generated OpenAPI schemas directly so the wire contract is preserved.

export type GraphSnapshot = components["schemas"]["GraphSnapshot"];
export type GraphPlan = components["schemas"]["GraphPlan"];
export type GraphCleared = components["schemas"]["GraphCleared"];
export type StrategyPatch = components["schemas"]["StrategyPatch"];
export type StrategyMeta = components["schemas"]["StrategyMeta"];
export type StrategyLink = components["schemas"]["StrategyLink"];
export type PlanArtifact = components["schemas"]["PlanArtifact"];
export type PlanUpdate = components["schemas"]["PlanUpdate"];
export type DecisionPresented = components["schemas"]["DecisionPresented"];
export type ProblemFramePart = components["schemas"]["ProblemFrame"];
export type GeneSetPart = components["schemas"]["GeneSet"];
export type OptimizationSnapshot = components["schemas"]["OptimizationSnapshot"];
export type PhaseChange = components["schemas"]["PhaseChange"];
export type ConversationTitle = components["schemas"]["ConversationTitle"];

/**
 * Per-data-part UIMessagePart types using AI SDK's custom data-part convention.
 * The protocol convention is: `data-<name>` where <name> matches the
 * kebab-case of the `type` string emitted by the backend's
 * `DataChunk(type="data-<name>")`.
 */
export type PathfinderDataParts = {
  "graph-snapshot": GraphSnapshot;
  "graph-plan": GraphPlan;
  "graph-cleared": GraphCleared;
  "strategy-patch": StrategyPatch;
  "strategy-meta": StrategyMeta;
  "strategy-link": StrategyLink;
  "plan-artifact": PlanArtifact;
  "plan-update": PlanUpdate;
  "decision-presented": DecisionPresented;
  "problem-frame": ProblemFramePart;
  "gene-set": GeneSetPart;
  "optimization-snapshot": OptimizationSnapshot;
  "phase-change": PhaseChange;
  "conversation-title": ConversationTitle;
};

/**
 * Metadata attached to a PathfinderUIMessage (populated incrementally via
 * MessageMetadataChunks during streaming).
 *
 * All fields are optional because metadata chunks arrive at different points
 * in a streaming turn — the first chunk may carry only `traceId` before
 * `model` and `phase` land. User and system messages legitimately have most
 * of these absent.
 *
 * For **completed assistant messages**, use `CompletedAssistantMetadata` and
 * the `assertCompletedAssistantMetadata` type guard: once the stream ends,
 * missing `phase` / `model` / `traceId` / `createdAt` is a bug we want to
 * surface loudly rather than silently paper over.
 */
export interface PathfinderMessageMetadata {
  phase?: "scoping" | "discovery" | "planning" | "execution" | "verification" | "completed";
  model?: string;
  tokensUsed?: number;
  tokensBudget?: number;
  conversationTitle?: string;
  traceId?: string;
  /** ISO 8601 timestamp of when the message was created server-side. */
  createdAt?: string;
}

/** A fully-hydrated assistant message's metadata — all required fields are present. */
export interface CompletedAssistantMetadata {
  phase: "scoping" | "discovery" | "planning" | "execution" | "verification" | "completed";
  model: string;
  traceId: string;
  createdAt: string;
  tokensUsed?: number;
  tokensBudget?: number;
  conversationTitle?: string;
}

/** The typed UIMessage alias used throughout the chat feature. */
export type PathfinderUIMessage = UIMessage<PathfinderMessageMetadata, PathfinderDataParts>;
