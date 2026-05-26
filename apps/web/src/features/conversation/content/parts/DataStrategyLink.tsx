import type { StrategyLink } from "@pathfinder/shared";

export function DataStrategyLink({ data }: { data: StrategyLink }) {
  return (
    <div
      data-testid="data-strategy-link"
      className="my-2 rounded-md border border-border bg-card px-3 py-2 text-sm"
    >
      <a
        href={data.url}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium text-primary underline-offset-2 hover:underline"
      >
        {data.title ?? `Strategy ${data.strategyId}`}
      </a>
    </div>
  );
}
