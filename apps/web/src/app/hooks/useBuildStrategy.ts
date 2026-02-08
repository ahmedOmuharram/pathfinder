import { useCallback, useState } from "react";
import {
  createStrategy,
  getStrategy,
  normalizePlan,
  pushStrategy,
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

  // Push always includes a build (save) step:
  // normalize plan -> persist -> push to WDK -> refresh.
  const buildAndPush = useCallback(async () => {
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
    const pushed = await pushStrategy(strategyId);
    // Refresh after push so we pick up server-updated steps (wdkStepId/resultCount).
    const refreshed = await getStrategy(strategyId);
    const built = {
      ...refreshed!,
      wdkStrategyId: pushed.wdkStrategyId,
      wdkUrl: pushed.wdkUrl,
    };
    addExecutedStrategy(built);
    setStrategyMeta({
      name: refreshed.name,
      recordType: refreshed.recordType,
      siteId: refreshed.siteId,
      createdAt: refreshed.createdAt,
    });
    setWdkInfo(
      pushed.wdkStrategyId,
      pushed.wdkUrl,
      refreshed.name,
      refreshed.description,
    );
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
        message: "Please log in to VEuPathDB to push strategies.",
      });
      return;
    }
    setIsBuilding(true);
    try {
      await buildAndPush();
      addToast({
        type: "success",
        message: `Strategy pushed to ${selectedSiteDisplayName}.`,
      });
    } catch (e) {
      addToast({
        type: "error",
        message: toUserMessage(e, `Failed to push to ${selectedSiteDisplayName}.`),
      });
    } finally {
      setIsBuilding(false);
    }
  }, [addToast, buildAndPush, planResult, selectedSiteDisplayName, veupathdbSignedIn]);

  return {
    isBuilding,
    handleBuild,
  };
}
