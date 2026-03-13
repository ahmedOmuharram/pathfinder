/**
 * Shared TypeScript types for Pathfinder - VEuPathDB Strategy Builder
 *
 * Canonical combine operators (matches WDK BooleanOperator): INTERSECT, MINUS,
 * RMINUS, LONLY, RONLY, COLOCATE, UNION.
 */

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

export interface ColocationParams {
  upstream: number;
  downstream: number;
  strand: "same" | "opposite" | "both";
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
  /**
   * Name of the WDK search/question to execute (search, transform, or boolean operator).
   */
  searchName: string;

  /**
   * Parameters passed to the underlying WDK question/search.
   *
   * - For leaf searches and transforms: the question parameters
   * - For combine/operator steps: typically includes operator param(s) in WDK, but we also
   *   store `operator` explicitly in the plan for convenience/validation.
   */
  parameters?: Record<string, unknown>;

  /**
   * Primary input step (unary/binary operations).
   */
  primaryInput?: PlanStepNode;

  /**
   * Secondary input step (binary operations).
   * When present, this node represents a combine operation.
   */
  secondaryInput?: PlanStepNode;

  /**
   * Required when `secondaryInput` is present.
   */
  operator?: CombineOperator;

  /**
   * Only relevant when operator is COLOCATE.
   */
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

// API Types

export interface RecordType {
  name: string;
  displayName: string;
  description?: string;
}

export interface Search {
  name: string;
  displayName: string;
  description?: string;
  recordType: string;
}

// Gene Search / Resolve Types

export interface GeneSearchResult {
  geneId: string;
  displayName: string;
  organism: string;
  product: string;
  matchedFields: string[];
  geneName?: string;
  geneType?: string;
  location?: string;
}

export interface GeneSearchResponse {
  results: GeneSearchResult[];
  totalCount: number;
  suggestedOrganisms?: string[];
}

export interface ResolvedGene {
  geneId: string;
  displayName: string;
  organism: string;
  product: string;
  geneName: string;
  geneType: string;
  location: string;
}

export interface GeneResolveResponse {
  resolved: ResolvedGene[];
  unresolved: string[];
}

// Strategy Types

export type StepKind = "search" | "transform" | "combine";

export interface Step {
  id: string;
  /**
   * Derived convenience field. Do not persist as source-of-truth.
   * Inferred from presence of input edges.
   */
  kind?: StepKind;
  displayName: string;
  /**
   * Name of the underlying WDK question/search for this step.
   *
   * For transforms and combines, this is still the WDK question name
   * (e.g. boolean_question_* or a transform question).
   */
  searchName?: string;
  recordType?: string;
  parameters?: Record<string, unknown>;
  operator?: CombineOperator;
  colocationParams?: ColocationParams;
  primaryInputStepId?: string;
  secondaryInputStepId?: string;
  resultCount?: number | null;
  wdkStepId?: number;
  filters?: StepFilter[];
  analyses?: StepAnalysis[];
  reports?: StepReport[];
  /** Set during graph editing when step has a validation issue. */
  validationError?: string;
}

export interface StepFilter {
  name: string;
  value: unknown;
  disabled?: boolean;
}

export interface StepAnalysis {
  analysisType: string;
  parameters?: Record<string, unknown>;
  customName?: string;
}

export interface StepReport {
  reportName: string;
  config?: Record<string, unknown>;
}

export interface Strategy {
  id: string;
  name: string;
  title?: string | null;
  description?: string | null;
  siteId: string;
  recordType: string | null;
  /** Full step list. Empty `[]` in list responses, populated in detail views. */
  steps: Step[];
  rootStepId: string | null;
  wdkStrategyId?: number;
  isSaved?: boolean;
  messages?: Message[];
  thinking?: Thinking;
  modelId?: string | null;
  createdAt: string;
  updatedAt: string;
  /** Convenience count — always set, avoids needing steps loaded. */
  stepCount?: number;
  /** Result count from root step. Present in list views. */
  resultCount?: number | null;
  /** URL to the strategy on the WDK site. */
  wdkUrl?: string | null;
  /** ISO datetime when strategy was dismissed (soft-deleted). null = active. */
  dismissedAt?: string | null;
}


// Chat Types

export type MessageRole = "user" | "assistant" | "system";

export type ModelProvider = "openai" | "anthropic" | "google" | "ollama";
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

/** An entry in the model catalog returned by GET /api/v1/models. */
export interface ModelCatalogEntry {
  id: string;
  name: string;
  provider: ModelProvider;
  model: string;
  supportsReasoning: boolean;
  enabled: boolean;
  contextSize: number;
  defaultReasoningBudget: number;
}

export type CitationSource =
  | "web"
  | "europepmc"
  | "crossref"
  | "openalex"
  | "semanticscholar"
  | "pubmed"
  | "arxiv"
  | "biorxiv"
  | "medrxiv"
  | "veupathdb";

export interface Citation {
  id: string;
  source: CitationSource;
  /**
   * Stable, model-friendly reference tag (BibTeX-ish).
   * The model can cite inline using \\cite{tag} or [@tag].
   */
  tag?: string | null;
  title: string;
  url?: string | null;
  authors?: string[] | null;
  year?: number | null;
  doi?: string | null;
  pmid?: string | null;
  snippet?: string | null;
  accessedAt?: string | null;
}

export interface PlanningArtifact {
  id: string;
  title: string;
  summaryMarkdown: string;
  assumptions: string[];
  parameters: Record<string, unknown>;
  proposedStrategyPlan?: StrategyPlan | Record<string, unknown> | null;
  createdAt: string;
}

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  result?: string | null;
}

export interface SubKaniActivity {
  calls: Record<string, ToolCall[]>;
  status: Record<string, string>;
}

export interface Thinking {
  toolCalls?: ToolCall[];
  /**
   * Completed tool calls from the last finalized turn.
   * (Used so Thinking/Reasoning survives refresh without implying streaming.)
   */
  lastToolCalls?: ToolCall[];
  subKaniCalls?: Record<string, ToolCall[]>;
  subKaniStatus?: Record<string, string>;
  reasoning?: string;
  updatedAt?: string;
}

export interface Message {
  role: MessageRole;
  content: string;
  toolCalls?: ToolCall[];
  subKaniActivity?: SubKaniActivity;
  citations?: Citation[];
  planningArtifacts?: PlanningArtifact[];
  /** Model reasoning text captured during the turn. */
  reasoning?: string | null;
  /** Final optimization progress snapshot for this turn. */
  optimizationProgress?: OptimizationProgressData | null;
  timestamp: string;
  /** Catalog model ID that generated this message (e.g. "openai/gpt-5"). */
  modelId?: string;
  reasoningEffort?: ReasoningEffort;
  /** @-mentions attached to a user message. */
  mentions?: ChatMention[];
  /** Token usage for this assistant turn. */
  tokenUsage?: TokenUsage;
}

export interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  toolCallCount: number;
  registeredToolCount: number;
}

export interface Conversation {
  id: string;
  siteId: string;
  title?: string;
  messages: Message[];
  strategyId: string;
  createdAt: string;
  updatedAt: string;
}

export interface ChatRequest {
  strategyId?: string;
  siteId: string;
  message: string;
}

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

export interface SearchValidationErrors {
  general: string[];
  byKey: Record<string, string[]>;
}

export interface SearchValidationPayload {
  isValid: boolean;
  normalizedContextValues: Record<string, unknown>;
  errors: SearchValidationErrors;
}

export interface SearchValidationResponse {
  validation: SearchValidationPayload;
}

export interface ParamSpec {
  name: string;
  displayName?: string;
  type: string;
  allowEmptyValue?: boolean;
  allowMultipleValues?: boolean;
  multiPick?: boolean;
  minSelectedCount?: number;
  maxSelectedCount?: number;
  countOnlyLeaves?: boolean;
  /** WDK default value for this parameter. */
  initialDisplayValue?: unknown;
  vocabulary?: unknown;
  /** Range for number/number-range params. */
  min?: number | null;
  max?: number | null;
  increment?: number | null;
  /**
   * ``true`` when the WDK marks a string-typed param as numeric
   * (``isNumber: true``).  Used to detect params like ``fold_change``
   * that have ``type: "string"`` but accept numeric input.
   */
  isNumber?: boolean;
  [key: string]: unknown;
}

// Strategy Requests/Responses

export interface StepCountsResponse {
  counts: Record<string, number | null>;
}

export interface OpenStrategyRequest {
  strategyId?: string;
  wdkStrategyId?: number;
  siteId?: string;
}

export interface OpenStrategyResponse {
  strategyId: string;
}

export interface CreateStrategyRequest {
  name: string;
  siteId: string;
  plan: StrategyPlan;
}

export interface UpdateStrategyRequest {
  name?: string;
  plan?: StrategyPlan;
  wdkStrategyId?: number | null;
}

export interface PushResult {
  wdkStrategyId: number;
  wdkUrl: string;
}


// Parameter Optimisation

export interface OptimizationTrial {
  trialNumber: number;
  parameters: Record<string, unknown>;
  score: number;
  recall: number | null;
  falsePositiveRate: number | null;
  resultCount: number | null;
  positiveHits: number | null;
  negativeHits: number | null;
  totalPositives: number | null;
  totalNegatives: number | null;
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

export interface OptimizationProgressData {
  optimizationId: string;
  status: OptimizationStatus;
  searchName?: string;
  recordType?: string;
  budget?: number;
  objective?: string;
  positiveControlsCount?: number;
  negativeControlsCount?: number;
  parameterSpace?: OptimizationParameterSpec[];
  currentTrial?: number;
  totalTrials?: number;
  trial?: OptimizationTrial;
  bestTrial?: OptimizationTrial | null;
  recentTrials?: OptimizationTrial[];
  allTrials?: OptimizationTrial[];
  paretoFrontier?: OptimizationTrial[];
  sensitivity?: Record<string, number>;
  totalTimeSeconds?: number;
  error?: string;
}

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

export interface ConfusionMatrix {
  truePositives: number;
  falsePositives: number;
  trueNegatives: number;
  falseNegatives: number;
}

export interface ExperimentMetrics {
  confusionMatrix: ConfusionMatrix;
  sensitivity: number;
  specificity: number;
  precision: number;
  negativePredictiveValue: number;
  falsePositiveRate: number;
  falseNegativeRate: number;
  f1Score: number;
  mcc: number;
  balancedAccuracy: number;
  youdensJ: number;
  totalResults: number;
  totalPositives: number;
  totalNegatives: number;
}

export interface GeneInfo {
  id: string;
  name?: string | null;
  organism?: string | null;
  product?: string | null;
}

export interface FoldMetrics {
  foldIndex: number;
  metrics: ExperimentMetrics;
  positiveControlIds: string[];
  negativeControlIds: string[];
}

export interface CrossValidationResult {
  k: number;
  folds: FoldMetrics[];
  meanMetrics: ExperimentMetrics;
  stdMetrics: Record<string, number>;
  overfittingScore: number;
  overfittingLevel: "low" | "moderate" | "high";
}

export interface EnrichmentTerm {
  termId: string;
  termName: string;
  geneCount: number;
  backgroundCount: number;
  foldEnrichment: number;
  oddsRatio: number;
  pValue: number;
  fdr: number;
  bonferroni: number;
  genes: string[];
}

export interface EnrichmentResult {
  analysisType: EnrichmentAnalysisType;
  terms: EnrichmentTerm[];
  totalGenesAnalyzed: number;
  backgroundSize: number;
  error?: string | null;
}

// Gene Set Types

export type GeneSetSource = "strategy" | "paste" | "upload" | "derived" | "saved";

export interface GeneSet {
  id: string;
  name: string;
  siteId: string;
  geneIds: string[];
  geneCount: number;
  source: GeneSetSource;
  wdkStrategyId?: number;
  wdkStepId?: number;
  searchName?: string;
  recordType?: string;
  parameters?: Record<string, unknown>;
  parentSetIds?: string[];
  operation?: string;
  stepCount?: number;
  createdAt?: string;
}

export interface OptimizeSpec {
  name: string;
  type: "numeric" | "integer" | "categorical";
  min?: number;
  max?: number;
  step?: number;
  choices?: string[];
}

// Rank-based evaluation types

export type ControlSetSource = "paper" | "curation" | "db_build" | "other";

export interface ControlSetSummary {
  id: string;
  name: string;
  source: ControlSetSource;
  tags: string[];
  positiveCount: number;
  negativeCount: number;
}

export interface ControlSet {
  id: string;
  name: string;
  siteId: string;
  recordType: string;
  positiveIds: string[];
  negativeIds: string[];
  source: ControlSetSource;
  tags: string[];
  provenanceNotes: string;
  version: number;
  isPublic: boolean;
  userId?: string | null;
  createdAt: string;
}

export interface RankMetrics {
  precisionAtK: Record<string, number>;
  recallAtK: Record<string, number>;
  enrichmentAtK: Record<string, number>;
  prCurve: [number, number][];
  listSizeVsRecall: [number, number][];
  totalResults: number;
}

export interface ConfidenceInterval {
  lower: number;
  mean: number;
  upper: number;
  std: number;
}

export interface NegativeSetVariant {
  label: string;
  negativeCount: number;
  rankMetrics: RankMetrics;
}

export interface BootstrapResult {
  nIterations: number;
  metricCis: Record<string, ConfidenceInterval>;
  rankMetricCis: Record<string, ConfidenceInterval>;
  topKStability: number;
  negativeSetSensitivity: NegativeSetVariant[];
}

// Tree optimization knob types

export interface ThresholdKnob {
  stepId: string;
  paramName: string;
  minVal: number;
  maxVal: number;
  stepSize?: number | null;
}

export interface OperatorKnob {
  combineNodeId: string;
  options: string[];
}

export interface TreeOptimizationTrial {
  trialNumber: number;
  parameters: Record<string, number | string>;
  score: number;
  rankMetrics: RankMetrics | null;
  listSize: number;
}

export interface TreeOptimizationResult {
  bestTrial: TreeOptimizationTrial | null;
  allTrials: TreeOptimizationTrial[];
  totalTimeSeconds: number;
  objective: string;
}

export interface ExperimentConfig {
  siteId: string;
  recordType: string;

  /** Experiment mode: single search, multi-step graph, or import from strategy. */
  mode?: ExperimentMode;

  /** Search name for single-step mode. */
  searchName: string;
  /** Parameters for single-step mode. */
  parameters: Record<string, unknown>;

  /**
   * Step tree for multi-step or import mode.
   * Each node follows the ``PlanStepNode`` shape (recursive).
   */
  stepTree?: PlanStepNode | null;
  /** Pathfinder strategy ID to import (import mode). */
  sourceStrategyId?: string | null;
  /** Which step node ID in the tree to optimise (multi-step mode). */
  optimizationTargetStep?: string | null;

  positiveControls: string[];
  negativeControls: string[];
  controlsSearchName: string;
  controlsParamName: string;
  controlsValueFormat?: string;
  enableCrossValidation: boolean;
  kFolds: number;
  enrichmentTypes: EnrichmentAnalysisType[];
  name: string;
  description?: string;
  optimizationSpecs?: OptimizeSpec[];
  parameterDisplayValues?: Record<string, string>;
  optimizationBudget?: number;
  optimizationObjective?: string;
  parentExperimentId?: string | null;
  enableStepAnalysis?: boolean;
  stepAnalysisPhases?: StepAnalysisPhase[];
  controlSetId?: string | null;
  thresholdKnobs?: ThresholdKnob[];
  operatorKnobs?: OperatorKnob[];
  treeOptimizationObjective?: string;
  treeOptimizationBudget?: number;
  maxListSize?: number | null;
  sortAttribute?: string | null;
  sortDirection?: "ASC" | "DESC";
  /** Pre-resolved gene IDs for direct evaluation (bypasses WDK step creation). */
  targetGeneIds?: string[] | null;
}

export interface OptimizationResult {
  optimizationId: string;
  status: string;
  bestTrial: OptimizationTrial | null;
  allTrials: OptimizationTrial[];
  paretoFrontier: OptimizationTrial[];
  sensitivity: Record<string, number>;
  totalTimeSeconds: number;
  totalTrials: number;
  errorMessage: string | null;
}

// Step Analysis Types (deterministic decomposition)

export type StepContributionVerdict = "essential" | "helpful" | "neutral" | "harmful";

export interface StepEvaluation {
  stepId: string;
  searchName: string;
  displayName: string;
  resultCount: number;
  positiveHits: number;
  positiveTotal: number;
  negativeHits: number;
  negativeTotal: number;
  recall: number;
  falsePositiveRate: number;
  capturedPositiveIds: string[];
  capturedNegativeIds: string[];
  tpMovement: number;
  fpMovement: number;
  fnMovement: number;
}

export interface OperatorVariant {
  operator: string;
  positiveHits: number;
  negativeHits: number;
  totalResults: number;
  recall: number;
  falsePositiveRate: number;
  f1Score: number;
}

export interface OperatorComparison {
  combineNodeId: string;
  currentOperator: string;
  variants: OperatorVariant[];
  recommendation: string;
  recommendedOperator: string;
  precisionAtKDelta: Record<string, number>;
}

export interface StepContribution {
  stepId: string;
  searchName: string;
  baselineRecall: number;
  ablatedRecall: number;
  recallDelta: number;
  baselineFpr: number;
  ablatedFpr: number;
  fprDelta: number;
  verdict: StepContributionVerdict;
  enrichmentDelta: number;
  narrative: string;
}

export interface ParameterSweepPoint {
  value: number;
  positiveHits: number;
  negativeHits: number;
  totalResults: number;
  recall: number;
  fpr: number;
  f1: number;
}

export interface ParameterSensitivity {
  stepId: string;
  paramName: string;
  currentValue: number;
  sweepPoints: ParameterSweepPoint[];
  recommendedValue: number;
  recommendation: string;
}

export interface StepAnalysisResult {
  stepEvaluations: StepEvaluation[];
  operatorComparisons: OperatorComparison[];
  stepContributions: StepContribution[];
  parameterSensitivities: ParameterSensitivity[];
}

export type StepAnalysisPhase =
  | "step_evaluation"
  | "operator_comparison"
  | "contribution"
  | "sensitivity";

export interface Experiment {
  id: string;
  config: ExperimentConfig;
  status: ExperimentStatus;
  metrics: ExperimentMetrics | null;
  crossValidation: CrossValidationResult | null;
  enrichmentResults: EnrichmentResult[];
  truePositiveGenes: GeneInfo[];
  falseNegativeGenes: GeneInfo[];
  falsePositiveGenes: GeneInfo[];
  trueNegativeGenes: GeneInfo[];
  optimizationResult: OptimizationResult | null;
  notes: string | null;
  batchId: string | null;
  benchmarkId: string | null;
  controlSetLabel: string | null;
  isPrimaryBenchmark: boolean;
  error: string | null;
  totalTimeSeconds: number | null;
  createdAt: string;
  completedAt: string | null;
  wdkStrategyId: number | null;
  wdkStepId: number | null;
  stepAnalysis: StepAnalysisResult | null;
  rankMetrics: RankMetrics | null;
  robustness: BootstrapResult | null;
  treeOptimization: TreeOptimizationResult | null;
}

export interface ExperimentSummary {
  id: string;
  name: string;
  siteId: string;
  searchName: string;
  recordType: string;
  mode?: ExperimentMode;
  status: ExperimentStatus;
  f1Score: number | null;
  sensitivity: number | null;
  specificity: number | null;
  totalPositives: number;
  totalNegatives: number;
  createdAt: string;
  batchId: string | null;
  benchmarkId: string | null;
  controlSetLabel: string | null;
  isPrimaryBenchmark: boolean;
}

export interface TrialProgressData {
  currentTrial: number;
  totalTrials: number;
  trial: {
    trialNumber: number;
    score: number;
    recall: number | null;
    falsePositiveRate: number | null;
    resultCount: number | null;
    parameters: Record<string, unknown>;
  };
  bestTrial: {
    trialNumber: number;
    score: number;
    parameters: Record<string, unknown>;
  } | null;
  recentTrials: {
    trialNumber: number;
    score: number;
  }[];
}

export interface StepAnalysisProgressData {
  phase: StepAnalysisPhase;
  message: string;
  current?: number;
  total?: number;
  stepEvaluation?: StepEvaluation;
  operatorComparison?: OperatorComparison;
  stepContribution?: StepContribution;
  parameterSensitivity?: ParameterSensitivity;
}

export interface ExperimentProgressData {
  experimentId: string;
  phase: ExperimentProgressPhase;
  message?: string;
  metrics?: ExperimentMetrics | null;
  cvFoldIndex?: number;
  cvTotalFolds?: number;
  enrichmentType?: EnrichmentAnalysisType;
  trialProgress?: TrialProgressData;
  stepAnalysisProgress?: StepAnalysisProgressData;
  error?: string;
}

// Classification for control test results
export type Classification = "TP" | "FP" | "FN" | "TN";

// Chat @-Mention References

export type ChatMentionType = "strategy" | "experiment";

export interface ChatMention {
  type: ChatMentionType;
  id: string;
  displayName: string;
}
