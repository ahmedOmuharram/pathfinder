"use client";

/**
 * Floating @-mention autocomplete dropdown.
 *
 * Shows strategies and experiments matching the user's query,
 * positioned relative to the textarea caret.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FileText, FlaskConical, Loader2 } from "lucide-react";
import type { ChatMention, ExperimentSummary } from "@pathfinder/shared";
import type { StrategyWithMeta } from "@/features/strategy/types";
import { listStrategies } from "@/lib/api/client";
import { listExperiments } from "@/features/experiments/api/crud";

interface MentionAutocompleteProps {
  siteId: string;
  query: string;
  /** Pixel position relative to the textarea container. */
  position: { top: number; left: number };
  visible: boolean;
  onSelect: (mention: ChatMention) => void;
  onDismiss: () => void;
}

interface MentionOption {
  mention: ChatMention;
  subtitle: string;
  icon: typeof FileText;
}

export function MentionAutocomplete({
  siteId,
  query,
  position,
  visible,
  onSelect,
  onDismiss,
}: MentionAutocompleteProps) {
  const [strategies, setStrategies] = useState<StrategyWithMeta[]>([]);
  const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [focusIndex, setFocusIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    let pending = 2;

    const done = () => {
      pending -= 1;
      if (pending <= 0 && !cancelled) setLoading(false);
    };

    const withTimeout = <T,>(p: Promise<T>, ms: number): Promise<T> =>
      Promise.race([
        p,
        new Promise<never>((_, rej) => setTimeout(() => rej(new Error("timeout")), ms)),
      ]);

    queueMicrotask(() => {
      if (!cancelled) setLoading(true);
    });

    withTimeout(listStrategies(siteId), 4000)
      .then((strats) => {
        if (!cancelled) setStrategies(strats.filter((s) => s.steps.length > 0));
      })
      .catch(() => {
        if (!cancelled) setStrategies([]);
      })
      .finally(done);

    withTimeout(listExperiments(siteId), 4000)
      .then((exps) => {
        if (!cancelled) setExperiments(exps.filter((e) => e.status === "completed"));
      })
      .catch(() => {
        if (!cancelled) setExperiments([]);
      })
      .finally(done);

    return () => {
      cancelled = true;
    };
  }, [visible, siteId]);

  const options = useMemo<MentionOption[]>(() => {
    const q = query.toLowerCase();
    const result: MentionOption[] = [];

    for (const s of strategies) {
      if (q && !s.name.toLowerCase().includes(q)) continue;
      result.push({
        mention: { type: "strategy", id: s.id, displayName: s.name },
        subtitle: `${s.steps.length} step${s.steps.length !== 1 ? "s" : ""}${s.recordType ? ` · ${s.recordType}` : ""}`,
        icon: FileText,
      });
    }

    for (const e of experiments) {
      const label = e.name || e.searchName;
      if (q && !label.toLowerCase().includes(q)) continue;
      const metrics = e.f1Score != null ? `F1=${e.f1Score.toFixed(2)}` : "";
      result.push({
        mention: { type: "experiment", id: e.id, displayName: label },
        subtitle: `${e.recordType}${metrics ? ` · ${metrics}` : ""}`,
        icon: FlaskConical,
      });
    }

    return result.slice(0, 10);
  }, [strategies, experiments, query]);

  useEffect(() => {
    queueMicrotask(() => setFocusIndex(0));
  }, [options.length, query]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!visible || options.length === 0) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setFocusIndex((i) => (i + 1) % options.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setFocusIndex((i) => (i - 1 + options.length) % options.length);
      } else if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        e.stopPropagation();
        onSelect(options[focusIndex].mention);
      } else if (e.key === "Escape") {
        e.preventDefault();
        onDismiss();
      }
    },
    [visible, options, focusIndex, onSelect, onDismiss],
  );

  useEffect(() => {
    if (!visible) return;
    document.addEventListener("keydown", handleKeyDown, true);
    return () => document.removeEventListener("keydown", handleKeyDown, true);
  }, [visible, handleKeyDown]);

  if (!visible) return null;

  return (
    <div
      ref={containerRef}
      className="absolute z-50 w-72 rounded-md border border-slate-200 bg-white shadow-lg"
      style={{ bottom: position.top, left: position.left }}
    >
      {loading && (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
        </div>
      )}
      {!loading && options.length === 0 && (
        <div className="px-3 py-3 text-center text-[11px] text-slate-400">
          {query ? "No matches" : "No strategies or experiments"}
        </div>
      )}
      {!loading &&
        options.map((opt, i) => {
          const Icon = opt.icon;
          return (
            <button
              key={`${opt.mention.type}-${opt.mention.id}`}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                onSelect(opt.mention);
              }}
              onMouseEnter={() => setFocusIndex(i)}
              className={`flex w-full items-center gap-2 px-3 py-2 text-left text-[12px] transition-colors ${
                i === focusIndex ? "bg-slate-100" : "hover:bg-slate-50"
              }`}
            >
              <Icon className="h-3.5 w-3.5 shrink-0 text-slate-400" />
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium text-slate-800">
                  {opt.mention.displayName}
                </div>
                <div className="truncate text-[10px] text-slate-400">
                  {opt.mention.type === "strategy" ? "Strategy" : "Experiment"} ·{" "}
                  {opt.subtitle}
                </div>
              </div>
            </button>
          );
        })}
    </div>
  );
}
