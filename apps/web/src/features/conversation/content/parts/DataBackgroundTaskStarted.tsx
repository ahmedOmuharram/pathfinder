import type { BackgroundTaskStarted } from "@pathfinder/shared";

export function DataBackgroundTaskStarted({ data }: { data: BackgroundTaskStarted }) {
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
        <span className="font-mono">{data.toolName}</span>
        <span className="mx-1">·</span>
        <span>~{minutes} min</span>
      </div>
    </div>
  );
}
