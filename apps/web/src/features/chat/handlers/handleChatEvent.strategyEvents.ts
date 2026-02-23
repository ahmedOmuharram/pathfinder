import type { StrategyStep } from "@/features/strategy/types";
import type { ChatEventContext } from "./handleChatEvent.types";

export function handleStrategyUpdateEvent(ctx: ChatEventContext, data: unknown) {
  const { step, graphId } = data as {
    graphId?: string;
    step: {
      stepId: string;
      kind?: string;
      displayName: string;
      searchName?: string;
      transformName?: string;
      operator?: string;
      primaryInputStepId?: string;
      secondaryInputStepId?: string;
      parameters?: Record<string, unknown>;
      name?: string | null;
      description?: string | null;
      recordType?: string;
      graphId?: string;
      graphName?: string;
    };
  };
  const targetGraphId = graphId || step?.graphId || ctx.strategyIdAtStart || null;
  if (!targetGraphId || !step) return;
  if (ctx.strategyIdAtStart && targetGraphId !== ctx.strategyIdAtStart) return;

  ctx.session.captureUndoSnapshot(targetGraphId);
  if (step?.name || step?.description || step?.recordType) {
    ctx.setStrategyMeta({
      name: step.graphName ?? step.name ?? undefined,
      description: step.description ?? undefined,
      recordType: step.recordType ?? undefined,
    });
  }
  if (!ctx.strategyIdAtStart || ctx.strategyIdAtStart === targetGraphId) {
    ctx.addStep({
      id: step.stepId,
      kind: (step.kind ?? "search") as StrategyStep["kind"],
      displayName: step.displayName || step.kind || "Untitled step",
      recordType: step.recordType ?? undefined,
      searchName: step.searchName,
      operator: (step.operator as StrategyStep["operator"]) ?? undefined,
      primaryInputStepId: step.primaryInputStepId,
      secondaryInputStepId: step.secondaryInputStepId,
      parameters: step.parameters,
    });
    ctx.session.markSnapshotApplied();
  }
}

export function handleGraphSnapshotEvent(ctx: ChatEventContext, data: unknown) {
  const { graphSnapshot } = data as {
    graphSnapshot?: Record<string, unknown>;
  };
  if (graphSnapshot) ctx.applyGraphSnapshot(graphSnapshot);
}

export function handleStrategyLinkEvent(ctx: ChatEventContext, data: unknown) {
  const { graphId, wdkStrategyId, wdkUrl, name, description, strategySnapshotId } =
    data as {
      graphId?: string;
      wdkStrategyId?: number;
      wdkUrl?: string;
      name?: string;
      description?: string;
      strategySnapshotId?: string;
    };
  const targetGraphId = graphId || strategySnapshotId || ctx.strategyIdAtStart;
  if (ctx.strategyIdAtStart && targetGraphId !== ctx.strategyIdAtStart) return;
  const isActive = !!targetGraphId;
  if (isActive && wdkStrategyId)
    ctx.setWdkInfo(wdkStrategyId, wdkUrl, name, description);
  if (isActive && targetGraphId) {
    ctx.setStrategyMeta({
      name: name ?? undefined,
      description: description ?? undefined,
    });
  }
  if (isActive && ctx.currentStrategy) {
    ctx.addExecutedStrategy({
      ...ctx.currentStrategy,
      name: name ?? ctx.currentStrategy.name,
      description: description ?? ctx.currentStrategy.description,
      wdkStrategyId: wdkStrategyId ?? ctx.currentStrategy.wdkStrategyId,
      wdkUrl: wdkUrl ?? ctx.currentStrategy.wdkUrl,
      updatedAt: new Date().toISOString(),
    });
  } else if (targetGraphId) {
    ctx
      .getStrategy(targetGraphId)
      .then((full) => ctx.addExecutedStrategy(full))
      .catch(() => {});
  }
}

export function handleStrategyMetaEvent(ctx: ChatEventContext, data: unknown) {
  const { graphId, name, description, recordType, graphName } = data as {
    graphId?: string;
    name?: string;
    description?: string;
    recordType?: string | null;
    graphName?: string;
  };
  const targetGraphId = graphId || ctx.strategyIdAtStart;
  if (!targetGraphId) return;
  if (ctx.strategyIdAtStart && targetGraphId !== ctx.strategyIdAtStart) return;
  ctx.setStrategyMeta({
    name: name ?? graphName ?? undefined,
    description: description ?? undefined,
    recordType: recordType ?? undefined,
  });
}

export function handleStrategyClearedEvent(ctx: ChatEventContext, data: unknown) {
  const { graphId } = data as { graphId?: string };
  const targetGraphId = graphId || ctx.strategyIdAtStart;
  if (
    !targetGraphId ||
    (ctx.strategyIdAtStart && targetGraphId !== ctx.strategyIdAtStart)
  )
    return;
  if (!ctx.strategyIdAtStart || targetGraphId === ctx.strategyIdAtStart) {
    ctx.clearStrategy();
  }
}
