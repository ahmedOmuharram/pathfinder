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

function VariantLane({ chunk }: { chunk: TaskProgressChunk }) {
  const variantId =
    chunk.toolSpecific != null
      ? (chunk.toolSpecific as Record<string, unknown>)["variantId"]
      : undefined;
  const label = typeof variantId === "string" ? variantId : chunk.taskId;
  const pct = Math.round(chunk.percent * 100);
  return (
    <div
      data-testid="variant-lane"
      className="rounded-md border border-border bg-muted/30 px-2 py-1.5"
    >
      <div className="mb-0.5 font-mono text-xs text-muted-foreground">{label}</div>
      <div className="text-xs">{chunk.message}</div>
      <div className="mt-0.5 flex items-center gap-1.5">
        <div className="flex-1">
          <ProgressBar percent={chunk.percent} />
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">{pct}%</span>
      </div>
    </div>
  );
}

function hasVariantId(chunk: TaskProgressChunk): boolean {
  if (chunk.toolSpecific == null) return false;
  const vid = (chunk.toolSpecific as Record<string, unknown>)["variantId"];
  return typeof vid === "string";
}

export function DataTaskProgress({
  data,
  variants,
}: {
  data: TaskProgressChunk;
  variants?: Map<string, TaskProgressChunk>;
}) {
  if (variants != null && variants.size > 0 && hasVariantId(data)) {
    return (
      <div
        data-testid="data-task-progress"
        className="my-1 grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-2"
      >
        {[...variants.entries()].map(([vid, chunk]) => (
          <VariantLane key={vid} chunk={chunk} />
        ))}
      </div>
    );
  }

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
