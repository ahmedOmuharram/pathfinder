import { useRef, useState } from "react";
import { toast } from "sonner";
import { useEventCallback } from "usehooks-ts";
import type { Strategy } from "@pathfinder/shared";
import { pushConversation } from "@/lib/api/conversations";
import { serializeStrategyAst } from "@/lib/strategyGraph/serialize";
import { useStrategyStore } from "@/state/strategy/store";
import { useSessionStore } from "@/state/useSessionStore";

type SyncStatus = "idle" | "syncing" | "synced" | "error";

interface UseAutoSyncArgs {
  strategy: Strategy | null;
  siteId: string;
}

interface UseAutoSyncResult {
  syncStatus: SyncStatus;
  lastSyncError: string | null;
  triggerSync: () => void;
}

// In-flight guard: if a sync is running when a new trigger arrives we drop
// the duplicate. The next user edit naturally re-triggers, so no self-retry
// loop is required.
export function useAutoSync(args: UseAutoSyncArgs): UseAutoSyncResult {
  const { strategy, siteId } = args;
  const [syncStatus, setSyncStatus] = useState<SyncStatus>("idle");
  const [lastSyncError, setLastSyncError] = useState<string | null>(null);
  const syncingRef = useRef(false);
  const setStrategyMeta = useStrategyStore((s) => s.setStrategyMeta);

  const triggerSync = useEventCallback(() => {
    const isAiStreaming = useSessionStore.getState().chatIsStreaming;
    if (isAiStreaming) return;
    if (!strategy || strategy.steps.length === 0) return;
    if (syncingRef.current) return;

    const draftStrategy = useStrategyStore.getState().strategy;
    if (!draftStrategy) return;

    const planResult = serializeStrategyAst(
      Object.fromEntries(draftStrategy.steps.map((s) => [s.id, s])),
      draftStrategy,
    );
    if (!planResult) return;

    syncingRef.current = true;
    setSyncStatus("syncing");

    pushConversation(draftStrategy.id, {
      name: draftStrategy.name || "Untitled Strategy",
      siteId,
      strategyAst: planResult.plan,
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
        toast.error(`Sync failed: ${msg}`);
      })
      .finally(() => {
        syncingRef.current = false;
      });
  });

  return { syncStatus, lastSyncError, triggerSync };
}
