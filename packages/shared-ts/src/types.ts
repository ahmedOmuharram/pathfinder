/**
 * Shared TypeScript types for Pathfinder - VEuPathDB Strategy Builder
 */

// Combine Operations

export const CombineOperator = {
  INTERSECT: "INTERSECT",
  UNION: "UNION",
  MINUS_LEFT: "MINUS_LEFT",
  MINUS_RIGHT: "MINUS_RIGHT",
  COLOCATE: "COLOCATE",
} as const;

export type CombineOperator =
  (typeof CombineOperator)[keyof typeof CombineOperator];

export const CombineOperatorLabels: Record<CombineOperator, string> = {
  INTERSECT: "IDs in common (AND)",
  UNION: "Combined (OR)",
  MINUS_LEFT: "Not in right",
  MINUS_RIGHT: "Not in left",
  COLOCATE: "Genomic colocation",
};

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
  steps: Step[];
  rootStepId: string | null;
  wdkStrategyId?: number;
  isSaved?: boolean;
  messages?: Message[];
  thinking?: Thinking;
  modelId?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface StrategySummary {
  id: string;
  name: string;
  title?: string | null;
  siteId: string;
  recordType: string | null;
  stepCount: number;
  resultCount?: number | null;
  wdkStrategyId?: number;
  isSaved?: boolean;
  createdAt: string;
  updatedAt: string;
}

// Chat Types

export type MessageRole = "user" | "assistant" | "system";

export type ChatMode = "execute" | "plan";

export type ModelProvider = "openai" | "anthropic" | "google";
export type ReasoningEffort = "none" | "low" | "medium" | "high";

/** Model selection passed with each chat request. */
export interface ModelSelection {
  provider?: ModelProvider;
  model?: string;
  reasoningEffort?: ReasoningEffort;
}

/** An entry in the model catalog returned by GET /api/v1/models. */
export interface ModelCatalogEntry {
  id: string;
  name: string;
  provider: ModelProvider;
  model: string;
  supportsReasoning: boolean;
  enabled: boolean;
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
  mode?: ChatMode;
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
  planSessionId?: string;
  siteId: string;
  message: string;
  mode?: ChatMode;
}

// Planning (plan sessions)

export interface PlanSessionSummary {
  id: string;
  siteId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

export interface PlanSession {
  id: string;
  siteId: string;
  title: string;
  messages?: Message[];
  thinking?: Thinking;
  planningArtifacts?: PlanningArtifact[];
  modelId?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface OpenPlanSessionRequest {
  planSessionId?: string;
  siteId: string;
  title?: string;
}

export interface OpenPlanSessionResponse {
  planSessionId: string;
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

export interface WdkStrategySummary {
  wdkStrategyId: number;
  name: string;
  siteId: string;
  wdkUrl?: string | null;
  rootStepId?: number | null;
  isSaved?: boolean;
  isInternal?: boolean;
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
}

export interface OptimizeSpec {
  name: string;
  type: "numeric" | "integer" | "categorical";
  min?: number;
  max?: number;
  step?: number;
  choices?: string[];
}

export interface ExperimentConfig {
  siteId: string;
  recordType: string;
  searchName: string;
  parameters: Record<string, unknown>;
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
}

export interface OptimizationTrialResult {
  trialNumber: number;
  parameters: Record<string, unknown>;
  score: number;
  recall: number | null;
  falsePositiveRate: number | null;
  resultCount: number | null;
}

export interface OptimizationResult {
  optimizationId: string;
  status: string;
  bestTrial: OptimizationTrialResult | null;
  allTrials: OptimizationTrialResult[];
  paretoFrontier: OptimizationTrialResult[];
  sensitivity: Record<string, number>;
  totalTimeSeconds: number;
  totalTrials: number;
  errorMessage: string | null;
}

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
  error: string | null;
  totalTimeSeconds: number | null;
  createdAt: string;
  completedAt: string | null;
  wdkStrategyId: number | null;
  wdkStepId: number | null;
}

export interface ExperimentSummary {
  id: string;
  name: string;
  siteId: string;
  searchName: string;
  recordType: string;
  status: ExperimentStatus;
  f1Score: number | null;
  sensitivity: number | null;
  specificity: number | null;
  totalPositives: number;
  totalNegatives: number;
  createdAt: string;
  batchId: string | null;
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

export interface ExperimentProgressData {
  experimentId: string;
  phase: ExperimentProgressPhase;
  message?: string;
  metrics?: ExperimentMetrics | null;
  cvFoldIndex?: number;
  cvTotalFolds?: number;
  enrichmentType?: EnrichmentAnalysisType;
  trialProgress?: TrialProgressData;
  error?: string;
}

// Chat @-Mention References

export type ChatMentionType = "strategy" | "experiment";

export interface ChatMention {
  type: ChatMentionType;
  id: string;
  displayName: string;
}
