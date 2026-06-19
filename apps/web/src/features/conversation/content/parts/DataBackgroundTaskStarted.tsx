"use client";

import type { BackgroundTaskStarted } from "@pathfinder/shared";

import { useConversationId } from "@/lib/hooks/useConversationId";
import { humanizeToolName } from "@/lib/utils/toolNames";

import { DataTaskCompleted } from "./DataTaskCompleted";
import { DataTaskProgress } from "./DataTaskProgress";
import { useTaskEventStream } from "./useTaskEventStream";

export function DataBackgroundTaskStarted({ data }: { data: BackgroundTaskStarted }) {
  const conversationId = useConversationId();
  const { latest, variants, completed } = useTaskEventStream(
    conversationId,
    data.taskId,
  );
  const minutes = Math.ceil(data.estimatedDurationSeconds / 60);
  return (
    <div
      data-testid="data-background-task-started"
      className="my-2 rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-xs"
    >
      <div className="flex items-center gap-2">
        <span className="inline-block size-2 animate-pulse rounded-full bg-primary" />
        <span className="font-medium">Background task started</span>
      </div>
      <div className="mt-1 text-muted-foreground">
        <span className="font-medium text-foreground">
          {humanizeToolName(data.toolName)}
        </span>
        <span className="mx-1">·</span>
        <span>~{minutes} min</span>
      </div>
      {completed === null && latest !== null ? (
        <DataTaskProgress data={latest} variants={variants} />
      ) : null}
      {completed !== null ? <DataTaskCompleted data={completed} /> : null}
    </div>
  );
}
