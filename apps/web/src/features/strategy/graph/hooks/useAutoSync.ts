import { useCallback, useEffect, useRef, useState } from "react";
import type { Strategy } from "@pathfinder/shared";
import { pushStrategy } from "@/lib/api/strategies";
import { serializeStrategyPlan } from "@/lib/strategyGraph/serialize";
import { useStrategyStore } from "@/state/strategy/store";
import { useSessionStore } from "@/state/useSessionStore";

type SyncStatus = "idle" | "syncing" | "synced" | "error";

interface UseAutoSyncArgs {
  strategy: Strategy | null;
  siteId: string;
  onToast?: (toast: {
    type: "success" | "error" | "warning" | "info";
    message: string;
  }) => void;
}

interface UseAutoSyncResult {
  syncStatus: SyncStatus;
  lastSyncError: string | null;
  triggerSync: () => void;
}

export function useAutoSync(args: UseAutoSyncArgs): UseAutoSyncResult {
  const { strategy, siteId, onToast } = args;
  const [syncStatus, setSyncStatus] = useState<SyncStatus>("idle");
  const [lastSyncError, setLastSyncError] = useState<string | null>(null);
  const syncingRef = useRef(false);
  const pendingRef = useRef(false);
  const setStrategyMeta = useStrategyStore((s) => s.setStrategyMeta);

  // Use a ref for the sync function so the .finally() re-trigger always
  // calls the latest version without creating a self-referencing useCallback.
  const syncRef = useRef<() => void>(() => {});

  const doSync = useCallback(() => {
    // Skip during AI streaming -- the executor handles its own sync.
    const isAiStreaming = useSessionStore.getState().chatIsStreaming;
    if (isAiStreaming) return;

    if (!strategy || strategy.steps.length === 0) return;

    // If already syncing, mark as pending so we sync again after.
    if (syncingRef.current) {
      pendingRef.current = true;
      return;
    }

    const draftStrategy = useStrategyStore.getState().strategy;
    if (!draftStrategy) return;

    const planResult = serializeStrategyPlan(
      Object.fromEntries(draftStrategy.steps.map((s) => [s.id, s])),
      draftStrategy,
    );
    if (!planResult) return; // No root or empty

    syncingRef.current = true;
    setSyncStatus("syncing");

    pushStrategy(draftStrategy.id, {
      name: draftStrategy.name || "Untitled Strategy",
      siteId,
      plan: planResult.plan,
      description: draftStrategy.description ?? null,
    })
      .then((updated) => {
        setSyncStatus("synced");
        setLastSyncError(null);
        // Update store with WDK data (step counts, wdkStepIds, validation)
        setStrategyMeta({
          wdkStrategyId: updated.wdkStrategyId ?? null,
          wdkUrl: updated.wdkUrl ?? null,
          steps: updated.steps,
          rootStepId: updated.rootStepId ?? null,
        });
      })
      .catch((err: unknown) => {
        setSyncStatus("error");
        const msg = err instanceof Error ? err.message : "Sync failed";
        setLastSyncError(msg);
        onToast?.({ type: "error", message: `Sync failed: ${msg}` });
      })
      .finally(() => {
        syncingRef.current = false;
        if (pendingRef.current) {
          pendingRef.current = false;
          // Re-trigger sync for changes that came in while we were syncing
          syncRef.current();
        }
      });
  }, [strategy, siteId, setStrategyMeta, onToast]);

  useEffect(() => {
    syncRef.current = doSync;
  }, [doSync]);

  return { syncStatus, lastSyncError, triggerSync: doSync };
}
