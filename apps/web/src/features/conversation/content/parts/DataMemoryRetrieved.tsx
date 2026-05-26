import type { DataMemoryRetrievedPayload } from "@pathfinder/shared";

export function DataMemoryRetrieved({
  data,
}: {
  data: DataMemoryRetrievedPayload;
}) {
  if (data.memories.length === 0) return null;
  return (
    <div
      data-testid="data-memory-retrieved"
      className="my-2 rounded-md border border-border bg-card px-3 py-2 text-xs"
    >
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        Recalled memories ({data.memories.length})
      </p>
      <ul className="mt-1 space-y-0.5">
        {data.memories.map((mem) => (
          <li key={mem.key} className="flex items-baseline gap-1.5">
            <span className="shrink-0 rounded bg-muted px-1 py-0.5 text-[10px] font-mono">
              {mem.kind}
            </span>
            <span className="truncate">{mem.name}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
