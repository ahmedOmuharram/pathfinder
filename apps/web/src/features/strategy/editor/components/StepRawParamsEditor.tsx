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
      <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
        <input
          type="checkbox"
          checked={showRaw}
          onChange={(event) => onShowRawChange(event.target.checked)}
          className="h-3.5 w-3.5 rounded border-input text-foreground"
        />
        Advanced editing (show raw JSON)
      </label>
      {showRaw && (
        <div>
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Parameters (JSON)
          </label>
          <textarea
            value={rawParams}
            onChange={(e) => onRawParamsChange(e.target.value)}
            rows={6}
            className="w-full rounded-md border border-border bg-card px-3 py-2 font-mono text-sm text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>
      )}
      {isLoading && (
        <p className="text-xs text-muted-foreground">Loading parameters...</p>
      )}
      {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
    </>
  );
}
