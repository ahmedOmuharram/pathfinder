import type { TaskProgressChunk } from "@pathfinder/shared";

function ProgressBar({ percent }: { percent: number }) {
  const pct = Math.round(percent * 100);
  return (
    <div className="mt-0.5 h-1 overflow-hidden rounded-full bg-muted">
      <div
        data-testid="progress-bar-fill"
        className="h-full rounded-full bg-blue-500 transition-all"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function DataTaskProgress({ data }: { data: TaskProgressChunk }) {
  const pct = Math.round(data.percent * 100);
  return (
    <div data-testid="data-task-progress" className="my-1 text-xs">
      <div className="flex items-center justify-between text-muted-foreground">
        <span>{data.message}</span>
        <span className="font-mono">{pct}%</span>
      </div>
      <ProgressBar percent={data.percent} />
    </div>
  );
}
