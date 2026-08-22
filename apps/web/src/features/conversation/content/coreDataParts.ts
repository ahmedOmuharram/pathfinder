import { DataBackgroundTaskStarted } from "./parts/DataBackgroundTaskStarted";
import { DataConversationTitle } from "./parts/DataConversationTitle";
import { DataMemoryRetrieved } from "./parts/DataMemoryRetrieved";
import { DataTaskCompleted } from "./parts/DataTaskCompleted";
import { DataTaskProgress } from "./parts/DataTaskProgress";
import { DataTurnStopped } from "./parts/DataTurnStopped";
import { SubAgentCallCard } from "./parts/SubAgentCallCard";
import type { DataPartComponentMap } from "./dataPartComponentMap";

/** Parts any assistant emits: turn state, usage, tasks, sub-agents, memory. */
export type CoreDataPartKind =
  | "data-sub-agent-call"
  | "data-sub-agent-step"
  | "data-background-task-started"
  | "data-task-progress"
  | "data-task-completed"
  | "data-memory-retrieved"
  | "data-conversation-title"
  | "data-scratchpad-updated"
  | "data-turn-usage"
  | "data-turn-status"
  | "data-turn-stopped"
  | "data-lead-usage";

export const coreDataPartComponents: DataPartComponentMap<CoreDataPartKind> = {
  "data-sub-agent-call": SubAgentCallCard,
  "data-sub-agent-step": () => null,
  "data-background-task-started": DataBackgroundTaskStarted,
  "data-task-progress": DataTaskProgress,
  "data-task-completed": DataTaskCompleted,
  "data-memory-retrieved": DataMemoryRetrieved,
  "data-conversation-title": DataConversationTitle,
  "data-scratchpad-updated": () => null,
  "data-turn-usage": () => null,
  "data-turn-status": () => null,
  "data-turn-stopped": DataTurnStopped,
  "data-lead-usage": () => null,
};
