import type {
  SearchSuggestion,
  ControlGeneSuggestion,
  ParamSuggestion,
  RunConfigSuggestion,
} from "../../suggestionParser";

export function PanelSuggestionCard({
  data,
  onApply,
}: {
  data: SearchSuggestion;
  onApply?: (s: SearchSuggestion) => void;
}) {
  const paramEntries = data.suggestedParameters
    ? Object.entries(data.suggestedParameters)
    : [];

  return (
    <div className="my-1.5 rounded-md border border-primary/20 bg-primary/5/40 p-2">
      <div className="flex items-start justify-between gap-1.5">
        <div className="min-w-0 flex-1">
          <div
            className="text-xs font-semibold text-foreground line-clamp-2"
            title={data.displayName}
          >
            {data.displayName}
          </div>
          <div
            className="truncate text-xs font-mono text-muted-foreground"
            title={`${data.searchName} · ${data.recordType}`}
          >
            {data.searchName} · {data.recordType}
          </div>
        </div>
        {onApply && (
          <button
            type="button"
            onClick={() => onApply(data)}
            className="shrink-0 rounded px-2 py-1 text-xs font-semibold bg-primary/10 text-primary hover:bg-primary/20 transition"
          >
            Use
          </button>
        )}
      </div>
      {data.rationale && (
        <p className="mt-1 text-xs italic text-muted-foreground">{data.rationale}</p>
      )}
      {paramEntries.length > 0 && (
        <div className="mt-1 space-y-0.5">
          {paramEntries.map(([key, val]) => (
            <div key={key} className="text-xs">
              <span className="font-mono text-muted-foreground">{key}:</span>{" "}
              <span className="text-foreground">{val}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function PanelGeneCard({
  data,
  isAdded,
  onAdd,
}: {
  data: ControlGeneSuggestion;
  isAdded: boolean;
  onAdd?: (geneId: string, role: "positive" | "negative") => void;
}) {
  const borderColor =
    data.role === "positive" ? "border-emerald-200" : "border-destructive/30";
  const bgColor = data.role === "positive" ? "bg-success/10/40" : "bg-destructive/5/40";
  const badgeColor =
    data.role === "positive"
      ? "bg-emerald-100 text-success"
      : "bg-red-100 text-destructive";

  return (
    <div className={`my-1.5 rounded-md border ${borderColor} ${bgColor} p-2`}>
      <div className="flex items-start justify-between gap-1.5">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-semibold text-foreground">{data.geneId}</span>
            {data.geneName && (
              <span className="text-xs text-muted-foreground">({data.geneName})</span>
            )}
            <span
              className={`rounded-full px-1.5 py-0.5 text-[8px] font-semibold ${badgeColor}`}
            >
              {data.role}
            </span>
          </div>
          {data.product && (
            <div className="mt-0.5 text-xs text-muted-foreground line-clamp-1">
              {data.product}
            </div>
          )}
        </div>
        {onAdd && !isAdded && (
          <button
            type="button"
            onClick={() => onAdd(data.geneId, data.role)}
            className={`shrink-0 rounded px-2 py-1 text-xs font-semibold transition ${
              data.role === "positive"
                ? "bg-emerald-100 text-success hover:bg-emerald-200"
                : "bg-red-100 text-destructive hover:bg-red-200"
            }`}
          >
            Add
          </button>
        )}
        {isAdded && (
          <span className="shrink-0 rounded px-2 py-1 text-xs font-semibold bg-muted text-muted-foreground">
            Added
          </span>
        )}
      </div>
      {data.rationale && (
        <p className="mt-1 text-xs italic text-muted-foreground">{data.rationale}</p>
      )}
    </div>
  );
}

export function PanelParamCard({
  data,
  onApply,
}: {
  data: ParamSuggestion;
  onApply?: (params: Record<string, string>) => void;
}) {
  const entries = Object.entries(data.parameters);
  if (entries.length === 0) return null;

  return (
    <div className="my-1.5 rounded-md border border-violet-200 bg-violet-50/40 p-2">
      <div className="flex items-start justify-between gap-1.5">
        <div className="text-xs font-semibold text-foreground">
          Parameter suggestion
        </div>
        {onApply && (
          <button
            type="button"
            onClick={() => onApply(data.parameters)}
            className="shrink-0 rounded px-2 py-1 text-xs font-semibold bg-violet-100 text-violet-700 hover:bg-violet-200 transition"
          >
            Apply
          </button>
        )}
      </div>
      <div className="mt-1 space-y-0.5">
        {entries.map(([key, val]) => (
          <div key={key} className="text-xs">
            <span className="font-mono text-muted-foreground">{key}:</span>{" "}
            <span className="text-foreground">{val}</span>
          </div>
        ))}
      </div>
      {data.rationale && (
        <p className="mt-1 text-xs italic text-muted-foreground">{data.rationale}</p>
      )}
    </div>
  );
}

export function PanelRunConfigCard({
  data,
  onApply,
}: {
  data: RunConfigSuggestion;
  onApply?: (config: RunConfigSuggestion) => void;
}) {
  const items: [string, string][] = [];
  if (data.name) items.push(["Name", data.name]);
  if (data.enableCrossValidation !== undefined)
    items.push([
      "Robustness analysis",
      data.enableCrossValidation ? "Enabled" : "Disabled",
    ]);
  if (data.kFolds !== undefined) items.push(["Subsets", String(data.kFolds)]);
  if (data.enrichmentTypes?.length)
    items.push(["Enrichment", data.enrichmentTypes.join(", ")]);

  if (items.length === 0) return null;

  return (
    <div className="my-1.5 rounded-md border border-amber-200 bg-amber-50/40 p-2">
      <div className="flex items-start justify-between gap-1.5">
        <div className="text-xs font-semibold text-foreground">Run configuration</div>
        {onApply && (
          <button
            type="button"
            onClick={() => onApply(data)}
            className="shrink-0 rounded px-2 py-1 text-xs font-semibold bg-amber-100 text-amber-700 hover:bg-amber-200 transition"
          >
            Apply
          </button>
        )}
      </div>
      <div className="mt-1 space-y-0.5">
        {items.map(([label, val]) => (
          <div key={label} className="text-xs">
            <span className="font-medium text-muted-foreground">{label}:</span>{" "}
            <span className="text-foreground">{val}</span>
          </div>
        ))}
      </div>
      {data.rationale && (
        <p className="mt-1 text-xs italic text-muted-foreground">{data.rationale}</p>
      )}
    </div>
  );
}
