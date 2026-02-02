"use client";

type StepRawParamsEditorProps = {
  showRaw: boolean;
  rawParams: string;
  error: string | null;
  isLoading: boolean;
  onShowRawChange: (nextValue: boolean) => void;
  onRawParamsChange: (nextValue: string) => void;
};

export function StepRawParamsEditor({
  showRaw,
  rawParams,
  error,
  isLoading,
  onShowRawChange,
  onRawParamsChange,
}: StepRawParamsEditorProps) {
  return (
    <>
      <label className="flex items-center gap-2 text-[11px] font-medium text-slate-500">
        <input
          type="checkbox"
          checked={showRaw}
          onChange={(event) => onShowRawChange(event.target.checked)}
          className="h-3.5 w-3.5 rounded border-slate-300 text-slate-900"
        />
        Advanced editing (show raw JSON)
      </label>
      {showRaw && (
        <div>
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Parameters (JSON)
          </label>
          <textarea
            value={rawParams}
            onChange={(e) => onRawParamsChange(e.target.value)}
            rows={6}
            className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 font-mono text-[12px] text-slate-800 focus:border-slate-300 focus:outline-none focus:ring-1 focus:ring-slate-200"
          />
        </div>
      )}
      {isLoading && (
        <p className="text-[11px] text-slate-500">Loading parameters...</p>
      )}
      {error && <p className="mt-1 text-[11px] text-red-500">{error}</p>}
    </>
  );
}
