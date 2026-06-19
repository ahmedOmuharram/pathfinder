import type { ComponentType } from "react";
import type { DataPartKind, DataPartPayloadMap } from "@pathfinder/shared";

import { DataBackgroundTaskStarted } from "./parts/DataBackgroundTaskStarted";
import { DataConversationTitle } from "./parts/DataConversationTitle";
import { DataGeneSet } from "./parts/DataGeneSet";
import { DataGraphCleared } from "./parts/DataGraphCleared";
import { DataGraphSnapshot } from "./parts/DataGraphSnapshot";
import { DataMemoryRetrieved } from "./parts/DataMemoryRetrieved";
import { DataProblemFrame } from "./parts/DataProblemFrame";
import { DataStrategyLink } from "./parts/DataStrategyLink";
import { DataStrategyMeta } from "./parts/DataStrategyMeta";
import { DataEnrichmentResults } from "./parts/DataEnrichmentResults";
import { DataTaskCompleted } from "./parts/DataTaskCompleted";
import { DataTaskProgress } from "./parts/DataTaskProgress";
import { DataToolApprovalRequest } from "./parts/DataToolApprovalRequest";
import { DataToolApprovalResult } from "./parts/DataToolApprovalResult";
import { DataTurnStopped } from "./parts/DataTurnStopped";
import { DataScoredComparison } from "./parts/DataScoredComparison";
import { DataVariantComparison } from "./parts/DataVariantComparison";
import { DataVerificationSummary } from "./parts/DataVerificationSummary";
import { SubAgentCallCard } from "./parts/SubAgentCallCard";

// Map every DataPartKind to its renderer component. Adding a new kind to
// DataPartKind without adding it here causes a TypeScript compile error
// because the mapped type requires every literal in the union.
export const dataPartComponents: {
  [K in DataPartKind]: ComponentType<{ data: DataPartPayloadMap[K] }>;
} = {
  "data-sub-agent-call": SubAgentCallCard,
  "data-sub-agent-step": () => null,
  "data-ledger-update": () => null,
  "data-background-task-started": DataBackgroundTaskStarted,
  "data-task-progress": DataTaskProgress,
  "data-task-completed": DataTaskCompleted,
  "data-enrichment-results": DataEnrichmentResults,
  "data-strategy-link": DataStrategyLink,
  "data-strategy-meta": DataStrategyMeta,
  "data-graph-snapshot": DataGraphSnapshot,
  "data-graph-cleared": DataGraphCleared,
  "data-problem-frame": DataProblemFrame,
  "data-plan-artifact": () => null,
  "data-variant-comparison": DataVariantComparison,
  "data-scored-comparison": DataScoredComparison,
  "data-tool-approval-request": DataToolApprovalRequest,
  "data-tool-approval-result": DataToolApprovalResult,
  "data-memory-retrieved": DataMemoryRetrieved,
  "data-gene-set": DataGeneSet,
  "data-verification-summary": DataVerificationSummary,
  "data-conversation-title": DataConversationTitle,
  "data-scratchpad-updated": () => null,
  "data-turn-usage": () => null,
  "data-turn-status": () => null,
  "data-turn-stopped": DataTurnStopped,
  "data-lead-usage": () => null,
};
