"use client";

/**
 * Floating @-mention autocomplete dropdown.
 *
 * Shows strategies and experiments matching the user's query,
 * positioned relative to the textarea caret.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FileText, FlaskConical, Loader2 } from "lucide-react";
import type {
  ChatMention,
  ExperimentSummary,
  StrategySummary,
} from "@pathfinder/shared";
import { useStrategyListStore } from "@/state/useStrategyListStore";
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
  const storeStrategies = useStrategyListStore((s) => s.strategies);
  const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);
  const [loadingExperiments, setLoadingExperiments] = useState(false);
  const [focusIndex, setFocusIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const strategies = useMemo(
    () => storeStrategies.filter((s) => s.stepCount > 0),
    [storeStrategies],
  );

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;

    queueMicrotask(() => {
      if (!cancelled) setLoadingExperiments(true);
    });

    listExperiments(siteId)
      .then((exps) => {
        if (!cancelled) setExperiments(exps.filter((e) => e.status === "completed"));
      })
      .catch(() => {
        if (!cancelled) setExperiments([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingExperiments(false);
      });

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
        subtitle: `${s.stepCount} step${s.stepCount !== 1 ? "s" : ""}${s.recordType ? ` · ${s.recordType}` : ""}`,
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
      className="absolute z-50 w-72 rounded-md border border-border bg-card shadow-lg"
      style={{ bottom: position.top, left: position.left }}
    >
      {loadingExperiments && options.length === 0 && (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        </div>
      )}
      {!loadingExperiments && options.length === 0 && (
        <div className="px-3 py-3 text-center text-xs text-muted-foreground">
          {query ? "No matches" : "No strategies or experiments"}
        </div>
      )}
      {options.map((opt, i) => {
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
            className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors ${
              i === focusIndex ? "bg-accent" : "hover:bg-accent"
            }`}
          >
            <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium text-foreground">
                {opt.mention.displayName}
              </div>
              <div className="truncate text-xs text-muted-foreground">
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
