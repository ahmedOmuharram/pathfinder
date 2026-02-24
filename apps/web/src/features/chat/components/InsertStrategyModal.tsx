"use client";

/**
 * InsertStrategyModal — lets the user select an existing strategy to inject
 * as context into a plan-mode conversation.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Modal } from "@/lib/components/Modal";
import { listStrategies } from "@/lib/api/client";
import type { StrategyWithMeta } from "@/features/strategy/types";
import { Loader2, Search } from "lucide-react";

interface InsertStrategyModalProps {
  open: boolean;
  siteId: string;
  onClose: () => void;
  /** Called when the user selects a strategy.  */
  onInsert: (strategy: StrategyWithMeta) => void;
}

export function InsertStrategyModal({
  open,
  siteId,
  onClose,
  onInsert,
}: InsertStrategyModalProps) {
  const [strategies, setStrategies] = useState<StrategyWithMeta[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const cancelRef = useRef<() => void>(undefined);
  useEffect(() => {
    cancelRef.current?.();
    if (!open) return;
    let cancelled = false;
    cancelRef.current = () => {
      cancelled = true;
    };

    const fetch = async () => {
      setLoading(true);
      setError(null);
      try {
        const list = await listStrategies(siteId);
        if (!cancelled) {
          setStrategies(list.filter((s) => s.steps && s.steps.length > 0));
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load strategies.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void fetch();

    return () => {
      cancelled = true;
    };
  }, [open, siteId]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return strategies;
    return strategies.filter((s) => s.name.toLowerCase().includes(q));
  }, [strategies, query]);

  const handleSelect = useCallback(
    (strategy: StrategyWithMeta) => {
      onInsert(strategy);
    },
    [onInsert],
  );

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Insert existing strategy"
      maxWidth="max-w-md"
    >
      <div className="flex flex-col gap-3 px-5 pb-5 pt-2">
        <p className="text-sm text-muted-foreground">
          Select a strategy to include as context in your conversation.
        </p>

        {/* Search input */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search strategies..."
            className="w-full rounded-md border border-border py-1.5 pl-8 pr-3 text-sm text-foreground placeholder:text-muted-foreground"
          />
        </div>

        {/* Strategy list */}
        <div className="max-h-[300px] min-h-[100px] overflow-y-auto rounded-md border border-border">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          )}
          {error && (
            <div className="px-3 py-4 text-center text-sm text-destructive">
              {error}
            </div>
          )}
          {!loading && !error && filtered.length === 0 && (
            <div className="px-3 py-4 text-center text-sm text-muted-foreground">
              {query.trim()
                ? "No strategies match your search."
                : "No strategies with steps found."}
            </div>
          )}
          {!loading &&
            !error &&
            filtered.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => handleSelect(s)}
                className="flex w-full items-center gap-3 border-b border-border px-3 py-2.5 text-left transition-colors last:border-b-0 hover:bg-accent"
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-foreground">
                    {s.name}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {s.steps.length} step{s.steps.length !== 1 ? "s" : ""}{" "}
                    {s.recordType && `· ${s.recordType}`}
                  </div>
                </div>
                <div className="shrink-0 text-xs text-muted-foreground">Select</div>
              </button>
            ))}
        </div>
      </div>
    </Modal>
  );
}
