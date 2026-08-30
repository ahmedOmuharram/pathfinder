"use client";

import { useQuery } from "@tanstack/react-query";
import type {
  BackgroundTaskStarted,
  TaskCompleted,
  TaskProgressChunk,
} from "@pathfinder/shared";
import { taskCompletedSchema } from "@pathfinder/shared/generated/zod/taskCompletedSchema";
import { taskProgressSchema } from "@pathfinder/shared/generated/zod/taskProgressSchema";

import { TaskRow, type TaskOutcome } from "@/lib/components/thread/TaskRow";
import { useConversationId } from "@/lib/hooks/useConversationId";
import { humanizeToolName } from "@/lib/utils/toolNames";

import { useChatHelpersOptional } from "../../runtime/chatHelpersContext";

interface MessageWithParts {
  readonly parts: readonly { readonly type: string; readonly data?: unknown }[];
}

interface TaskLifecycle {
  progress: TaskProgressChunk | null;
  completed: TaskCompleted | null;
}

/**
 * Read one task's progress and outcome from the thread's own parts. The log
 * carries both on the message that started the task, so the card survives a
 * reload with no subscription.
 */
function collectTaskLifecycle(
  messages: readonly MessageWithParts[],
  taskId: string,
): TaskLifecycle {
  const lifecycle: TaskLifecycle = { progress: null, completed: null };
  for (const message of messages) {
    for (const part of message.parts) {
      if (part.type === "data-task-progress") {
        const parsed = taskProgressSchema.safeParse(part.data);
        if (parsed.success && parsed.data.taskId === taskId) {
          lifecycle.progress = parsed.data;
        }
      } else if (part.type === "data-task-completed") {
        const parsed = taskCompletedSchema.safeParse(part.data);
        if (parsed.success && parsed.data.taskId === taskId) {
          lifecycle.completed = parsed.data;
        }
      }
    }
  }
  return lifecycle;
}

export function DataBackgroundTaskStarted({ data }: { data: BackgroundTaskStarted }) {
  const conversationId = useConversationId();
  const chat = useChatHelpersOptional();
  const { progress, completed } = collectTaskLifecycle(
    chat?.messages ?? [],
    data.taskId,
  );

  // A suspended turn closes its own stream, so the task's progress, its outcome
  // and the continuation reach this page only on a fresh tail of the thread.
  useQuery({
    queryKey: ["conversations", conversationId, "tasks", data.taskId, "reattach"],
    queryFn: async () => {
      await chat?.resumeStream();
      return data.taskId;
    },
    enabled: completed === null && chat?.status === "ready",
    staleTime: Infinity,
    gcTime: Infinity,
    retry: false,
  });

  const row = (
    <TaskRow
      label={humanizeToolName(data.toolName)}
      percent={completed === null ? (progress?.percent ?? null) : 1}
      message={progress?.message ?? null}
      estimatedSeconds={data.estimatedDurationSeconds}
      outcome={outcomeOf(completed)}
      error={completed?.error ?? null}
    />
  );
  return (
    <div data-testid="data-background-task-started">
      {completed === null ? row : <div data-testid="data-task-completed">{row}</div>}
    </div>
  );
}

function outcomeOf(completed: TaskCompleted | null): TaskOutcome {
  if (completed === null) return "running";
  return completed.status === "success" ? "success" : "failure";
}
