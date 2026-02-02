import { useCallback, useState } from "react";
import {
  createStrategy,
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
  planHash: string | null;
  lastBuiltStrategyId: string | null;
  isDirty: boolean;
  veupathdbSignedIn: boolean;
  addExecutedStrategy: (strategy: StrategyWithMeta) => void;
  setStrategyMeta: (meta: Partial<StrategyWithMeta>) => void;
  setWdkInfo: (
    wdkStrategyId: number,
    wdkUrl?: string | null,
    name?: string | null,
    description?: string | null
  ) => void;
  setBuiltInfo: (strategyId: string, planHash: string) => void;
  addToast: (toast: { type: "success" | "error" | "warning" | "info"; message: string }) => void;
}

export function useBuildStrategy({
  selectedSite,
  selectedSiteDisplayName,
  strategy,
  planResult,
  planHash,
  lastBuiltStrategyId,
  isDirty,
  veupathdbSignedIn,
  addExecutedStrategy,
  setStrategyMeta,
  setWdkInfo,
  setBuiltInfo,
  addToast,
}: UseBuildStrategyArgs) {
  const [isBuilding, setIsBuilding] = useState(false);
  const [showBuildModal, setShowBuildModal] = useState(false);

  const buildWithRebuild = useCallback(async () => {
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
    const built = {
      ...created!,
      wdkStrategyId: pushed.wdkStrategyId,
      wdkUrl: pushed.wdkUrl,
    };
    addExecutedStrategy(built);
    setStrategyMeta({
      name: created.name,
      recordType: created.recordType,
      siteId: created.siteId,
      createdAt: created.createdAt,
    });
    setWdkInfo(pushed.wdkStrategyId, pushed.wdkUrl, created.name, created.description);
    if (planHash) {
      setBuiltInfo(created.id, planHash);
    }
  }, [
    addExecutedStrategy,
    planResult,
    planHash,
    selectedSite,
    setBuiltInfo,
    setStrategyMeta,
    setWdkInfo,
    strategy,
  ]);

  const buildWithoutRebuild = useCallback(async () => {
    if (!lastBuiltStrategyId) {
      await buildWithRebuild();
      return;
    }
    const pushed = await pushStrategy(lastBuiltStrategyId);
    const base = strategy;
    const built = {
      id: lastBuiltStrategyId,
      name: base?.name || planResult?.name || "Strategy",
      siteId: base?.siteId || selectedSite,
      recordType: base?.recordType || planResult?.recordType || "gene",
      steps: base?.steps || strategy?.steps || [],
      rootStepId: base?.rootStepId || strategy?.rootStepId || "",
      description: base?.description,
      createdAt: base?.createdAt || new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      wdkStrategyId: pushed.wdkStrategyId,
      wdkUrl: pushed.wdkUrl,
    };
    addExecutedStrategy(built);
    setStrategyMeta({
      name: built.name,
      recordType: built.recordType,
      siteId: built.siteId,
    });
    setWdkInfo(pushed.wdkStrategyId, pushed.wdkUrl, built.name, built.description);
  }, [
    addExecutedStrategy,
    buildWithRebuild,
    lastBuiltStrategyId,
    planResult?.name,
    planResult?.recordType,
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
    if (isDirty && lastBuiltStrategyId) {
      setShowBuildModal(true);
      return;
    }
    setIsBuilding(true);
    try {
      await buildWithRebuild();
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
  }, [
    addToast,
    buildWithRebuild,
    isDirty,
    lastBuiltStrategyId,
    planResult,
    selectedSiteDisplayName,
    veupathdbSignedIn,
  ]);

  const handlePushWithoutRebuild = useCallback(async () => {
    setShowBuildModal(false);
    setIsBuilding(true);
    try {
      await buildWithoutRebuild();
      addToast({
        type: "success",
        message: `Pushed to ${selectedSiteDisplayName} without rebuild.`,
      });
    } catch (e) {
      addToast({
        type: "error",
        message: toUserMessage(e, `Failed to push to ${selectedSiteDisplayName}.`),
      });
    } finally {
      setIsBuilding(false);
    }
  }, [addToast, buildWithoutRebuild, selectedSiteDisplayName]);

  const handleRebuildAndPush = useCallback(async () => {
    setShowBuildModal(false);
    setIsBuilding(true);
    try {
      await buildWithRebuild();
      addToast({
        type: "success",
        message: `Rebuilt and pushed to ${selectedSiteDisplayName}.`,
      });
    } catch (e) {
      addToast({
        type: "error",
        message: toUserMessage(e, `Failed to push to ${selectedSiteDisplayName}.`),
      });
    } finally {
      setIsBuilding(false);
    }
  }, [addToast, buildWithRebuild, selectedSiteDisplayName]);

  return {
    isBuilding,
    showBuildModal,
    setShowBuildModal,
    handleBuild,
    handlePushWithoutRebuild,
    handleRebuildAndPush,
  };
}
