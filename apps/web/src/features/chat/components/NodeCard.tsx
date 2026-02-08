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
        isSelected ? "border-slate-900 bg-white" : "border-slate-200 bg-white"
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
          {typeLabel}
        </span>
        <span
          className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
            isSelected
              ? "border-slate-900 bg-slate-900 text-white"
              : "border-slate-200 bg-slate-50 text-slate-500"
          }`}
        >
          {isSelected ? "Selected" : "Context"}
        </span>
        {node.operator && (
          <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            {node.operator}
          </span>
        )}
      </div>
      <div className="mt-1 text-sm font-medium text-slate-900">
        {node.displayName || "Untitled step"}
      </div>
      {node.searchName && (
        <div className="mt-0.5 text-[11px] text-slate-500">{node.searchName}</div>
      )}
    </div>
  );
}
