export type ChatNodeCardData = {
  type?: string;
  kind?: string;
  displayName?: string;
  searchName?: string;
  operator?: string;
  selected?: boolean;
};

export function NodeCard({ node }: { node: ChatNodeCardData }) {
  const isSelected = Boolean(node.selected);
  const kind = node.kind || node.type;
  const typeLabel =
    kind === "search"
      ? "Search"
      : kind === "combine"
        ? "Combine"
        : kind === "transform"
          ? "Transform"
          : "Step";

  return (
    <div
      className={`rounded-md border px-3 py-2 text-left ${
        isSelected ? "border-primary bg-card" : "border-border bg-card"
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="rounded-full border border-border bg-muted px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {typeLabel}
        </span>
        <span
          className={`rounded-full border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${
            isSelected
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border bg-muted text-muted-foreground"
          }`}
        >
          {isSelected ? "Selected" : "Context"}
        </span>
        {node.operator && (
          <span className="rounded-md border border-border bg-muted px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {node.operator}
          </span>
        )}
      </div>
      <div className="mt-1 text-sm font-medium text-foreground">
        {node.displayName || "Untitled step"}
      </div>
      {node.searchName && (
        <div className="mt-0.5 text-xs text-muted-foreground">{node.searchName}</div>
      )}
    </div>
  );
}
