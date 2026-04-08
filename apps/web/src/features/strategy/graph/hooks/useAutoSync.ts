import { useRef, useState } from "react";
import { useEventCallback } from "usehooks-ts";
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

  const doSyncRef = useRef<() => void>(() => {});
  const retrigger = useEventCallback(() => doSyncRef.current());

  const doSync = () => {
    const isAiStreaming = useSessionStore.getState().chatIsStreaming;
    if (isAiStreaming) return;

    if (!strategy || strategy.steps.length === 0) return;

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
    if (!planResult) return;

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
          retrigger();
        }
      });
  };

  doSyncRef.current = doSync;

  return { syncStatus, lastSyncError, triggerSync: doSync };
}
