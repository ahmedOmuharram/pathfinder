import { useState, useEffect, useCallback } from "react";
import type { ControlSet } from "@pathfinder/shared";
import type { ResolvedGene } from "@/lib/api/client";
import type { BenchmarkControlSetInput } from "../../../api/streaming";
import { listControlSets } from "../../../api/controlSets";
import { Button } from "@/lib/components/ui/Button";
import { Layers, Plus, Search, Star, Trash2, X } from "lucide-react";

/* ── GeneIdTextarea ──────────────────────────────────────────────── */

/** Parses comma- or newline-separated gene IDs from raw text. */
function parseGeneIds(raw: string): string[] {
  return raw
    .split(/[\n,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * A textarea that lets users freely type commas and newlines.
 * IDs are parsed on blur (not on every keystroke) so delimiters aren't
 * consumed mid-typing.
 */
function GeneIdTextarea({
  ids,
  onIdsChange,
  placeholder,
}: {
  ids: string[];
  onIdsChange: (ids: string[]) => void;
  placeholder: string;
}) {
  const [text, setText] = useState(() => ids.join("\n"));
  const [prevIds, setPrevIds] = useState(ids);

  // Sync from parent when the ids prop changes externally (e.g. loading a
  // saved control set). Uses render-time state adjustment instead of useEffect.
  if (ids !== prevIds) {
    setPrevIds(ids);
    const currentIds = parseGeneIds(text);
    if (JSON.stringify(currentIds) !== JSON.stringify(ids)) {
      setText(ids.join("\n"));
    }
  }

  const handleBlur = () => {
    const parsed = parseGeneIds(text);
    setPrevIds(parsed);
    onIdsChange(parsed);
    // Normalize the displayed text to one-id-per-line after blur
    setText(parsed.join("\n"));
  };

  return (
    <textarea
      rows={2}
      placeholder={placeholder}
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={handleBlur}
      className="w-full rounded border border-border bg-background px-2 py-1 text-[10px] font-mono placeholder:text-muted-foreground/60 focus:border-primary focus:outline-none"
    />
  );
}

export interface ControlsSectionProps {
  siteId: string;
  positiveGenes: ResolvedGene[];
  onPositiveGenesChange: (genes: ResolvedGene[]) => void;
  negativeGenes: ResolvedGene[];
  onNegativeGenesChange: (genes: ResolvedGene[]) => void;
  onOpenControlsModal: () => void;
  benchmarkMode: boolean;
  onBenchmarkModeChange: (v: boolean) => void;
  benchmarkControlSets: BenchmarkControlSetInput[];
  onBenchmarkControlSetsChange: (v: BenchmarkControlSetInput[]) => void;
}

/* ── BenchmarkControlSetsEditor ───────────────────────────────────── */

function BenchmarkControlSetsEditor({
  controlSets,
  onChange,
  savedControlSets,
}: {
  controlSets: BenchmarkControlSetInput[];
  onChange: (v: BenchmarkControlSetInput[]) => void;
  savedControlSets: ControlSet[];
}) {
  const addInline = useCallback(() => {
    onChange([
      ...controlSets,
      {
        label: `Set ${controlSets.length + 1}`,
        positiveControls: [],
        negativeControls: [],
        isPrimary: controlSets.length === 0,
      },
    ]);
  }, [controlSets, onChange]);

  const addFromSaved = useCallback(
    (cs: ControlSet) => {
      if (controlSets.some((s) => s.controlSetId === cs.id)) return;
      onChange([
        ...controlSets,
        {
          label: cs.name,
          positiveControls: cs.positiveIds,
          negativeControls: cs.negativeIds,
          controlSetId: cs.id,
          isPrimary: controlSets.length === 0,
        },
      ]);
    },
    [controlSets, onChange],
  );

  const remove = useCallback(
    (idx: number) => {
      const next = controlSets.filter((_, i) => i !== idx);
      if (next.length > 0 && !next.some((s) => s.isPrimary)) {
        next[0] = { ...next[0], isPrimary: true };
      }
      onChange(next);
    },
    [controlSets, onChange],
  );

  const setPrimary = useCallback(
    (idx: number) => {
      onChange(controlSets.map((s, i) => ({ ...s, isPrimary: i === idx })));
    },
    [controlSets, onChange],
  );

  const updateLabel = useCallback(
    (idx: number, label: string) => {
      onChange(controlSets.map((s, i) => (i === idx ? { ...s, label } : s)));
    },
    [controlSets, onChange],
  );

  const updateIds = useCallback(
    (idx: number, field: "positiveControls" | "negativeControls", ids: string[]) => {
      onChange(controlSets.map((s, i) => (i === idx ? { ...s, [field]: ids } : s)));
    },
    [controlSets, onChange],
  );

  return (
    <div className="space-y-2">
      <p className="text-[10px] text-muted-foreground">
        Add multiple control sets to benchmark your strategy. One must be marked as
        Primary for the main verdict.
      </p>

      {controlSets.map((cs, idx) => (
        <div
          key={idx}
          className={`relative space-y-1.5 rounded-md border p-2 ${
            cs.isPrimary
              ? "border-amber-400/50 bg-amber-50/50 dark:border-amber-600/30 dark:bg-amber-950/30"
              : "border-border bg-muted/30"
          }`}
        >
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setPrimary(idx)}
              title={cs.isPrimary ? "Primary benchmark" : "Set as primary"}
              className={`shrink-0 ${cs.isPrimary ? "text-amber-500" : "text-muted-foreground/40 hover:text-amber-400"}`}
            >
              <Star className={`h-3 w-3 ${cs.isPrimary ? "fill-current" : ""}`} />
            </button>
            <input
              type="text"
              value={cs.label}
              onChange={(e) => updateLabel(idx, e.target.value)}
              className="flex-1 rounded border border-border bg-background px-2 py-0.5 text-[11px] focus:border-primary focus:outline-none"
              placeholder="Label"
            />
            <button
              type="button"
              onClick={() => remove(idx)}
              className="shrink-0 text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="h-3 w-3" />
            </button>
          </div>
          {!cs.controlSetId && (
            <>
              <GeneIdTextarea
                ids={cs.positiveControls}
                onIdsChange={(ids) => updateIds(idx, "positiveControls", ids)}
                placeholder="Positive gene IDs (comma or newline separated)"
              />
              <GeneIdTextarea
                ids={cs.negativeControls}
                onIdsChange={(ids) => updateIds(idx, "negativeControls", ids)}
                placeholder="Negative gene IDs (comma or newline separated)"
              />
            </>
          )}
          {cs.controlSetId && (
            <p className="text-[10px] text-muted-foreground">
              Saved set: {cs.positiveControls.length} positive,{" "}
              {cs.negativeControls.length} negative
            </p>
          )}
        </div>
      ))}

      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          className="flex-1 border-dashed text-[10px]"
          onClick={addInline}
        >
          <Plus className="h-3 w-3" />
          Add inline
        </Button>
        {savedControlSets.length > 0 && (
          <select
            className="flex-1 rounded-md border border-dashed border-border bg-background px-2 py-1 text-[10px]"
            value=""
            onChange={(e) => {
              const cs = savedControlSets.find((s) => s.id === e.target.value);
              if (cs) addFromSaved(cs);
            }}
          >
            <option value="">+ Add saved set</option>
            {savedControlSets.map((cs) => (
              <option key={cs.id} value={cs.id}>
                {cs.name} ({cs.positiveIds.length}+ / {cs.negativeIds.length}-)
              </option>
            ))}
          </select>
        )}
      </div>
    </div>
  );
}

/* ── ControlsSection ──────────────────────────────────────────────── */

export function ControlsSection({
  siteId,
  positiveGenes,
  onPositiveGenesChange,
  negativeGenes,
  onNegativeGenesChange,
  onOpenControlsModal,
  benchmarkMode,
  onBenchmarkModeChange,
  benchmarkControlSets,
  onBenchmarkControlSetsChange,
}: ControlsSectionProps) {
  const [savedControlSets, setSavedControlSets] = useState<ControlSet[]>([]);

  useEffect(() => {
    if (benchmarkMode && siteId) {
      listControlSets(siteId)
        .then(setSavedControlSets)
        .catch(() => {});
    }
  }, [benchmarkMode, siteId]);

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Controls
        </h4>
        <label className="flex items-center gap-1.5 text-[10px] font-medium text-muted-foreground">
          <input
            type="checkbox"
            checked={benchmarkMode}
            onChange={(e) => onBenchmarkModeChange(e.target.checked)}
            className="rounded border-input"
          />
          <Layers className="h-3 w-3" />
          Benchmark suite
        </label>
      </div>

      {!benchmarkMode ? (
        <>
          <Button
            variant="outline"
            size="sm"
            className="mb-2 w-full border-dashed"
            onClick={onOpenControlsModal}
          >
            <Search className="h-3 w-3" />
            {positiveGenes.length + negativeGenes.length > 0
              ? "Edit Control Genes"
              : "Find Control Genes"}
          </Button>

          {positiveGenes.length > 0 && (
            <div data-testid="positive-controls-input" className="mb-2">
              <label className="mb-1 block text-[10px] text-muted-foreground">
                Positive ({positiveGenes.length})
              </label>
              <div className="flex flex-wrap gap-1">
                {positiveGenes.slice(0, 8).map((g) => (
                  <span
                    key={g.geneId}
                    className="inline-flex items-center gap-1 rounded bg-green-500/10 px-1.5 py-0.5 text-[10px] text-green-700 dark:text-green-400"
                  >
                    {g.geneId}
                    <button
                      onClick={() =>
                        onPositiveGenesChange(
                          positiveGenes.filter((x) => x.geneId !== g.geneId),
                        )
                      }
                      className="hover:text-destructive"
                    >
                      <X className="h-2.5 w-2.5" />
                    </button>
                  </span>
                ))}
                {positiveGenes.length > 8 && (
                  <span className="text-[10px] text-muted-foreground">
                    +{positiveGenes.length - 8} more
                  </span>
                )}
              </div>
            </div>
          )}

          {negativeGenes.length > 0 && (
            <div data-testid="negative-controls-input">
              <label className="mb-1 block text-[10px] text-muted-foreground">
                Negative ({negativeGenes.length})
              </label>
              <div className="flex flex-wrap gap-1">
                {negativeGenes.slice(0, 8).map((g) => (
                  <span
                    key={g.geneId}
                    className="inline-flex items-center gap-1 rounded bg-red-500/10 px-1.5 py-0.5 text-[10px] text-red-700 dark:text-red-400"
                  >
                    {g.geneId}
                    <button
                      onClick={() =>
                        onNegativeGenesChange(
                          negativeGenes.filter((x) => x.geneId !== g.geneId),
                        )
                      }
                      className="hover:text-destructive"
                    >
                      <X className="h-2.5 w-2.5" />
                    </button>
                  </span>
                ))}
                {negativeGenes.length > 8 && (
                  <span className="text-[10px] text-muted-foreground">
                    +{negativeGenes.length - 8} more
                  </span>
                )}
              </div>
            </div>
          )}
        </>
      ) : (
        <BenchmarkControlSetsEditor
          controlSets={benchmarkControlSets}
          onChange={onBenchmarkControlSetsChange}
          savedControlSets={savedControlSets}
        />
      )}
    </div>
  );
}
