import { DataBackgroundTaskStarted } from "./parts/DataBackgroundTaskStarted";
import { DataConversationTitle } from "./parts/DataConversationTitle";
import { DataMemoryRetrieved } from "./parts/DataMemoryRetrieved";
import { DataTurnFailed } from "./parts/DataTurnFailed";
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
  | "data-turn-failed"
  | "data-lead-usage";

export const coreDataPartComponents: DataPartComponentMap<CoreDataPartKind> = {
  "data-sub-agent-call": SubAgentCallCard,
  "data-sub-agent-step": () => null,
  "data-background-task-started": DataBackgroundTaskStarted,
  // The started card renders a task's progress and outcome from the message.
  "data-task-progress": () => null,
  "data-task-completed": () => null,
  "data-memory-retrieved": DataMemoryRetrieved,
  "data-conversation-title": DataConversationTitle,
  "data-scratchpad-updated": () => null,
  "data-turn-usage": () => null,
  "data-turn-status": () => null,
  "data-turn-stopped": DataTurnStopped,
  "data-turn-failed": DataTurnFailed,
  "data-lead-usage": () => null,
};
