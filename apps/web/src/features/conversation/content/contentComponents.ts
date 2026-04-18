import type { ComponentType } from "react";
import type { DataPartKind, DataPartPayloadMap } from "@pathfinder/shared";

import { DataPhaseStart } from "./parts/DataPhaseStart";
import { DataPhaseChange } from "./parts/DataPhaseChange";
import { DataBackgroundTaskStarted } from "./parts/DataBackgroundTaskStarted";
import { DataTaskProgress } from "./parts/DataTaskProgress";
import { DataTaskCompleted } from "./parts/DataTaskCompleted";
import { DataStrategyLink } from "./parts/DataStrategyLink";
import { DataProblemFrame } from "./parts/DataProblemFrame";
import { DataPlanArtifact } from "./parts/DataPlanArtifact";
import { DataToolApprovalRequest } from "./parts/DataToolApprovalRequest";
import { DataToolApprovalResult } from "./parts/DataToolApprovalResult";
import { DataMemoryRetrieved } from "./parts/DataMemoryRetrieved";
import { DataGeneSetCreated } from "./parts/DataGeneSetCreated";
import { DataVerificationSummary } from "./parts/DataVerificationSummary";
import { DataConversationTitle } from "./parts/DataConversationTitle";
import { DataTurnRejected } from "./parts/DataTurnRejected";
import { DataTurnQa } from "./parts/DataTurnQa";
import { DataSupervisorDecision } from "./parts/DataSupervisorDecision";

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
  "data-problem-frame": DataProblemFrame,
  "data-plan-artifact": DataPlanArtifact,
  "data-tool-approval-request": DataToolApprovalRequest,
  "data-tool-approval-result": DataToolApprovalResult,
  "data-memory-retrieved": DataMemoryRetrieved,
  "data-gene-set-created": DataGeneSetCreated,
  "data-verification-summary": DataVerificationSummary,
  "data-conversation-title": DataConversationTitle,
  "data-turn-rejected": DataTurnRejected,
  "data-turn-qa": DataTurnQa,
  "data-supervisor-decision": DataSupervisorDecision,
};
