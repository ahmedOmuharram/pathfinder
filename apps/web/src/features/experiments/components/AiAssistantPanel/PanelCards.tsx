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
    <div className="my-1.5 rounded-md border border-indigo-200 bg-indigo-50/40 p-2">
      <div className="flex items-start justify-between gap-1.5">
        <div className="min-w-0 flex-1">
          <div
            className="text-[10px] font-semibold text-slate-800 line-clamp-2"
            title={data.displayName}
          >
            {data.displayName}
          </div>
          <div
            className="truncate text-[9px] font-mono text-slate-400"
            title={`${data.searchName} · ${data.recordType}`}
          >
            {data.searchName} · {data.recordType}
          </div>
        </div>
        {onApply && (
          <button
            type="button"
            onClick={() => onApply(data)}
            className="shrink-0 rounded px-2 py-1 text-[9px] font-semibold bg-indigo-100 text-indigo-700 hover:bg-indigo-200 transition"
          >
            Use
          </button>
        )}
      </div>
      {data.rationale && (
        <p className="mt-1 text-[9px] italic text-slate-500">{data.rationale}</p>
      )}
      {paramEntries.length > 0 && (
        <div className="mt-1 space-y-0.5">
          {paramEntries.map(([key, val]) => (
            <div key={key} className="text-[9px]">
              <span className="font-mono text-slate-500">{key}:</span>{" "}
              <span className="text-slate-700">{val}</span>
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
    data.role === "positive" ? "border-emerald-200" : "border-red-200";
  const bgColor = data.role === "positive" ? "bg-emerald-50/40" : "bg-red-50/40";
  const badgeColor =
    data.role === "positive"
      ? "bg-emerald-100 text-emerald-700"
      : "bg-red-100 text-red-700";

  return (
    <div className={`my-1.5 rounded-md border ${borderColor} ${bgColor} p-2`}>
      <div className="flex items-start justify-between gap-1.5">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-semibold text-slate-800">
              {data.geneId}
            </span>
            {data.geneName && (
              <span className="text-[9px] text-slate-500">({data.geneName})</span>
            )}
            <span
              className={`rounded-full px-1.5 py-0.5 text-[8px] font-semibold ${badgeColor}`}
            >
              {data.role}
            </span>
          </div>
          {data.product && (
            <div className="mt-0.5 text-[9px] text-slate-500 line-clamp-1">
              {data.product}
            </div>
          )}
        </div>
        {onAdd && !isAdded && (
          <button
            type="button"
            onClick={() => onAdd(data.geneId, data.role)}
            className={`shrink-0 rounded px-2 py-1 text-[9px] font-semibold transition ${
              data.role === "positive"
                ? "bg-emerald-100 text-emerald-700 hover:bg-emerald-200"
                : "bg-red-100 text-red-700 hover:bg-red-200"
            }`}
          >
            Add
          </button>
        )}
        {isAdded && (
          <span className="shrink-0 rounded px-2 py-1 text-[9px] font-semibold bg-slate-100 text-slate-400">
            Added
          </span>
        )}
      </div>
      {data.rationale && (
        <p className="mt-1 text-[9px] italic text-slate-500">{data.rationale}</p>
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
        <div className="text-[10px] font-semibold text-slate-800">
          Parameter suggestion
        </div>
        {onApply && (
          <button
            type="button"
            onClick={() => onApply(data.parameters)}
            className="shrink-0 rounded px-2 py-1 text-[9px] font-semibold bg-violet-100 text-violet-700 hover:bg-violet-200 transition"
          >
            Apply
          </button>
        )}
      </div>
      <div className="mt-1 space-y-0.5">
        {entries.map(([key, val]) => (
          <div key={key} className="text-[9px]">
            <span className="font-mono text-slate-500">{key}:</span>{" "}
            <span className="text-slate-700">{val}</span>
          </div>
        ))}
      </div>
      {data.rationale && (
        <p className="mt-1 text-[9px] italic text-slate-500">{data.rationale}</p>
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
        <div className="text-[10px] font-semibold text-slate-800">
          Run configuration
        </div>
        {onApply && (
          <button
            type="button"
            onClick={() => onApply(data)}
            className="shrink-0 rounded px-2 py-1 text-[9px] font-semibold bg-amber-100 text-amber-700 hover:bg-amber-200 transition"
          >
            Apply
          </button>
        )}
      </div>
      <div className="mt-1 space-y-0.5">
        {items.map(([label, val]) => (
          <div key={label} className="text-[9px]">
            <span className="font-medium text-slate-500">{label}:</span>{" "}
            <span className="text-slate-700">{val}</span>
          </div>
        ))}
      </div>
      {data.rationale && (
        <p className="mt-1 text-[9px] italic text-slate-500">{data.rationale}</p>
      )}
    </div>
  );
}
