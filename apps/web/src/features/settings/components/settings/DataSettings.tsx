"use client";

/**
 * DataSettings -- destructive data-clearing actions (strategies, plans, all data).
 */

import { useState, useCallback } from "react";
import { useSettingsStore } from "@/state/useSettingsStore";
import { listStrategies, deleteStrategy, deletePlanSession } from "@/lib/api/client";
import { useAsyncAction } from "@/lib/utils/asyncAction";
import { Loader2, Trash2 } from "lucide-react";

interface DataSettingsProps {
  siteId: string;
  onPlansCleared?: () => void;
  onStrategiesCleared?: () => void;
}

export function DataSettings({
  siteId,
  onPlansCleared,
  onStrategiesCleared,
}: DataSettingsProps) {
  const [clearing, setClearing] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<string | null>(null);
  const { run, error } = useAsyncAction();
  const resetToDefaults = useSettingsStore((s) => s.resetToDefaults);

  const clearStrategies = useCallback(async () => {
    setClearing("strategies");
    await run(async () => {
      const all = await listStrategies(siteId);
      await Promise.allSettled(all.map((s) => deleteStrategy(s.id)));
      onStrategiesCleared?.();
    });
    setClearing(null);
    setConfirmAction(null);
  }, [siteId, onStrategiesCleared, run]);

  const clearPlans = useCallback(async () => {
    setClearing("plans");
    await run(async () => {
      // Plans are scoped to user; we need to fetch via the API.
      // Using a batch delete approach.
      const { requestJson } = await import("@/lib/api/http");
      const plans = await requestJson<{ id: string }[]>(
        `/api/v1/plans?siteId=${encodeURIComponent(siteId)}`,
      );
      await Promise.allSettled(plans.map((p) => deletePlanSession(p.id)));
      onPlansCleared?.();
    });
    setClearing(null);
    setConfirmAction(null);
  }, [siteId, onPlansCleared, run]);

  const clearAll = useCallback(async () => {
    setClearing("all");
    await run(async () => {
      await clearStrategies();
      await clearPlans();
      resetToDefaults();
    });
    setClearing(null);
    setConfirmAction(null);
  }, [clearStrategies, clearPlans, resetToDefaults, run]);

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <DangerAction
        label="Clear all plans"
        description="Delete all planning sessions for the current site."
        loading={clearing === "plans"}
        confirmed={confirmAction === "plans"}
        onConfirm={() => setConfirmAction("plans")}
        onExecute={clearPlans}
        onCancel={() => setConfirmAction(null)}
      />

      <DangerAction
        label="Clear all strategies"
        description="Delete all draft strategies for the current site."
        loading={clearing === "strategies"}
        confirmed={confirmAction === "strategies"}
        onConfirm={() => setConfirmAction("strategies")}
        onExecute={clearStrategies}
        onCancel={() => setConfirmAction(null)}
      />

      <DangerAction
        label="Clear all data"
        description="Delete all plans, strategies, and reset settings."
        loading={clearing === "all"}
        confirmed={confirmAction === "all"}
        onConfirm={() => setConfirmAction("all")}
        onExecute={clearAll}
        onCancel={() => setConfirmAction(null)}
      />
    </div>
  );
}

// --- DangerAction (internal to DataSettings) ---

function DangerAction({
  label,
  description,
  loading,
  confirmed,
  onConfirm,
  onExecute,
  onCancel,
}: {
  label: string;
  description: string;
  loading: boolean;
  confirmed: boolean;
  onConfirm: () => void;
  onExecute: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2.5">
      <div>
        <div className="text-sm font-medium text-foreground">{label}</div>
        <div className="text-xs text-muted-foreground">{description}</div>
      </div>
      {confirmed ? (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="rounded-md border border-border px-2 py-1 text-xs font-medium text-muted-foreground transition hover:bg-muted disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onExecute}
            disabled={loading}
            className="inline-flex items-center gap-1 rounded-md bg-red-600 px-2 py-1 text-xs font-medium text-white transition hover:bg-red-700 disabled:opacity-60"
          >
            {loading && <Loader2 className="h-3 w-3 animate-spin" />}
            Confirm
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={onConfirm}
          className="inline-flex items-center gap-1 rounded-md border border-destructive/30 px-2 py-1 text-xs font-medium text-destructive transition hover:bg-destructive/5"
        >
          <Trash2 className="h-3 w-3" />
          {label}
        </button>
      )}
    </div>
  );
}
