import type { StrategyWithMeta } from "@/types/strategy";
import { buildDraftStrategySummary } from "@/features/strategy/utils/draftSummary";

export async function openAndHydrateDraftStrategy(args: {
  siteId: string;
  open: () => Promise<{ strategyId: string }>;
  getStrategy: (strategyId: string) => Promise<StrategyWithMeta>;
  nowIso: () => string;
  setStrategyId: (strategyId: string | null) => void;
  addStrategy: (summary: ReturnType<typeof buildDraftStrategySummary>) => void;
  clearStrategy: () => void;
  setStrategy: (strategy: StrategyWithMeta) => void;
  setStrategyMeta: (meta: {
    name: string;
    recordType?: string;
    siteId: string;
  }) => void;
  onHydrateSuccess?: (full: StrategyWithMeta) => void;
  onHydrateError?: (error: unknown, strategyId: string) => void;
  cleanupOnHydrateError?: (strategyId: string) => void;
}): Promise<{ strategyId: string; full: StrategyWithMeta }> {
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
    setStrategyMeta({
      name: full.name,
      recordType: full.recordType ?? undefined,
      siteId: full.siteId,
    });
    onHydrateSuccess?.(full);
    return { strategyId: nextId, full };
  } catch (error) {
    onHydrateError?.(error, nextId);
    cleanupOnHydrateError?.(nextId);
    clearStrategy();
    throw error;
  }
}
