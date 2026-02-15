import { useCallback, useState } from "react";
import {
  createStrategy,
  getStrategy,
  normalizePlan,
  updateStrategy,
} from "@/lib/api/client";
import { toUserMessage } from "@/lib/api/errors";
import type { StrategyPlan } from "@pathfinder/shared";
import type { StrategyWithMeta } from "@/types/strategy";

interface UseBuildStrategyArgs {
  selectedSite: string;
  selectedSiteDisplayName: string;
  strategy: StrategyWithMeta | null;
  planResult: { plan: StrategyPlan; name: string; recordType: string | null } | null;
  veupathdbSignedIn: boolean;
  addExecutedStrategy: (strategy: StrategyWithMeta) => void;
  setStrategyMeta: (meta: Partial<StrategyWithMeta>) => void;
  setWdkInfo: (
    wdkStrategyId: number,
    wdkUrl?: string | null,
    name?: string | null,
    description?: string | null,
  ) => void;
  addToast: (toast: {
    type: "success" | "error" | "warning" | "info";
    message: string;
  }) => void;
}

export function useBuildStrategy({
  selectedSite,
  selectedSiteDisplayName,
  strategy,
  planResult,
  veupathdbSignedIn,
  addExecutedStrategy,
  setStrategyMeta,
  setWdkInfo,
  addToast,
}: UseBuildStrategyArgs) {
  const [isBuilding, setIsBuilding] = useState(false);

  /**
   * Build (save) the strategy locally. Auto-push to WDK happens server-side.
   * New strategies are created as drafts (isSaved=false).
   */
  const buildStrategy = useCallback(async () => {
    if (!planResult) return;
    const normalized = await normalizePlan(selectedSite, planResult.plan);
    const canonicalPlan = normalized.plan;
    let created = strategy;
    let strategyId = strategy?.id;
    if (strategyId) {
      created = await updateStrategy(strategyId, {
        name: planResult.name,
        plan: canonicalPlan,
      });
    } else {
      created = await createStrategy({
        name: planResult.name,
        siteId: selectedSite,
        plan: canonicalPlan,
      });
      strategyId = created.id;
    }
    // Refresh after save so we pick up server-updated steps (wdkStepId/resultCount).
    const refreshed = await getStrategy(strategyId);
    addExecutedStrategy(refreshed);
    setStrategyMeta({
      name: refreshed.name,
      recordType: refreshed.recordType,
      siteId: refreshed.siteId,
      createdAt: refreshed.createdAt,
    });
    if (refreshed.wdkStrategyId) {
      setWdkInfo(
        refreshed.wdkStrategyId,
        refreshed.wdkUrl,
        refreshed.name,
        refreshed.description,
      );
    }
  }, [
    addExecutedStrategy,
    planResult,
    selectedSite,
    setStrategyMeta,
    setWdkInfo,
    strategy,
  ]);

  const handleBuild = useCallback(async () => {
    if (!planResult) return;
    if (!veupathdbSignedIn) {
      addToast({
        type: "warning",
        message: "Please log in to VEuPathDB to build strategies.",
      });
      return;
    }
    setIsBuilding(true);
    try {
      await buildStrategy();
      addToast({
        type: "success",
        message: `Strategy saved as draft on ${selectedSiteDisplayName}.`,
      });
    } catch (e) {
      addToast({
        type: "error",
        message: toUserMessage(
          e,
          `Failed to save strategy on ${selectedSiteDisplayName}.`,
        ),
      });
    } finally {
      setIsBuilding(false);
    }
  }, [addToast, buildStrategy, planResult, selectedSiteDisplayName, veupathdbSignedIn]);

  return {
    isBuilding,
    handleBuild,
  };
}
