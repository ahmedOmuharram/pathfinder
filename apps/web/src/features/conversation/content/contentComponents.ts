import type { ComponentType } from "react";
import type { DataPartKind, DataPartPayloadMap } from "@pathfinder/shared";

import { DataBackgroundTaskStarted } from "./parts/DataBackgroundTaskStarted";
import { DataConversationTitle } from "./parts/DataConversationTitle";
import { DataDecisionPresented } from "./parts/DataDecisionPresented";
import { DataGeneSet } from "./parts/DataGeneSet";
import { DataGraphCleared } from "./parts/DataGraphCleared";
import { DataGraphPlan } from "./parts/DataGraphPlan";
import { DataGraphSnapshot } from "./parts/DataGraphSnapshot";
import { DataMemoryRetrieved } from "./parts/DataMemoryRetrieved";
import { DataPhaseChange } from "./parts/DataPhaseChange";
import { DataPhaseStart } from "./parts/DataPhaseStart";
import { DataPlanArtifact } from "./parts/DataPlanArtifact";
import { DataProblemFrame } from "./parts/DataProblemFrame";
import { DataStrategyLink } from "./parts/DataStrategyLink";
import { DataStrategyMeta } from "./parts/DataStrategyMeta";
import { DataStrategyUpdate } from "./parts/DataStrategyUpdate";
import { DataSupervisorDecision } from "./parts/DataSupervisorDecision";
import { DataTaskCompleted } from "./parts/DataTaskCompleted";
import { DataTaskProgress } from "./parts/DataTaskProgress";
import { DataToolApprovalRequest } from "./parts/DataToolApprovalRequest";
import { DataToolApprovalResult } from "./parts/DataToolApprovalResult";
import { DataTurnQa } from "./parts/DataTurnQa";
import { DataTurnRejected } from "./parts/DataTurnRejected";
import { DataVerificationSummary } from "./parts/DataVerificationSummary";

// Map every DataPartKind to its renderer component. Adding a new kind to
// DataPartKind without adding it here causes a TypeScript compile error
// because the mapped type requires every literal in the union.
export const dataPartComponents: {
  [K in DataPartKind]: ComponentType<{ data: DataPartPayloadMap[K] }>;
} = {
  "data-phase-start": DataPhaseStart,
  "data-phase-change": DataPhaseChange,
  "data-background-task-started": DataBackgroundTaskStarted,
  "data-task-progress": DataTaskProgress,
  "data-task-completed": DataTaskCompleted,
  "data-strategy-link": DataStrategyLink,
  "data-strategy-update": DataStrategyUpdate,
  "data-strategy-meta": DataStrategyMeta,
  "data-graph-snapshot": DataGraphSnapshot,
  "data-graph-cleared": DataGraphCleared,
  "data-graph-plan": DataGraphPlan,
  "data-problem-frame": DataProblemFrame,
  "data-plan-artifact": DataPlanArtifact,
  "data-decision-presented": DataDecisionPresented,
  "data-tool-approval-request": DataToolApprovalRequest,
  "data-tool-approval-result": DataToolApprovalResult,
  "data-memory-retrieved": DataMemoryRetrieved,
  "data-gene-set": DataGeneSet,
  "data-verification-summary": DataVerificationSummary,
  "data-conversation-title": DataConversationTitle,
  "data-turn-rejected": DataTurnRejected,
  "data-turn-qa": DataTurnQa,
  "data-supervisor-decision": DataSupervisorDecision,
  "data-scratchpad-updated": () => null,
};
