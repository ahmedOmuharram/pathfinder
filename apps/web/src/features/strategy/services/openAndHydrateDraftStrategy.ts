import type { Strategy } from "@pathfinder/shared";
import { buildDraftStrategySummary } from "@/features/strategy/utils/draftSummary";

export async function openAndHydrateDraftStrategy(args: {
  siteId: string;
  open: () => Promise<{ strategyId: string }>;
  getStrategy: (strategyId: string) => Promise<Strategy>;
  nowIso: () => string;
  setStrategyId: (strategyId: string | null) => void;
  addStrategy: (summary: ReturnType<typeof buildDraftStrategySummary>) => void;
  clearStrategy: () => void;
  setStrategy: (strategy: Strategy) => void;
  setStrategyMeta: (meta: {
    name: string;
    recordType?: string;
    siteId: string;
  }) => void;
  onHydrateSuccess?: (full: Strategy) => void;
  onHydrateError?: (error: unknown, strategyId: string) => void;
  cleanupOnHydrateError?: (strategyId: string) => void;
}): Promise<{ strategyId: string; full: Strategy }> {
  const {
    siteId,
    open,
    getStrategy,
    nowIso,
    setStrategyId,
    addStrategy,
    clearStrategy,
    setStrategy,
    setStrategyMeta,
    onHydrateSuccess,
    onHydrateError,
    cleanupOnHydrateError,
  } = args;

  const response = await open();
  const nextId = response.strategyId;

  setStrategyId(nextId);
  addStrategy(buildDraftStrategySummary({ id: nextId, siteId, nowIso }));
  clearStrategy();

  try {
    const full = await getStrategy(nextId);
    setStrategy(full);
    const meta: { name: string; recordType?: string; siteId: string } = {
      name: full.name,
      siteId: full.siteId,
    };
    if (full.recordType != null) {
      meta.recordType = full.recordType;
    }
    setStrategyMeta(meta);
    onHydrateSuccess?.(full);
    return { strategyId: nextId, full };
  } catch (error) {
    onHydrateError?.(error, nextId);
    cleanupOnHydrateError?.(nextId);
    clearStrategy();
    throw error;
  }
}
