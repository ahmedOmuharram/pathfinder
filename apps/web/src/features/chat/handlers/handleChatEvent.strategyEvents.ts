import type { Step } from "@pathfinder/shared";
import type {
  StrategyActions,
  StreamContext,
  EventHelpers,
} from "./handleChatEvent.types";
import type {
  StrategyUpdateData,
  GraphSnapshotData,
  StrategyLinkData,
  StrategyMetaData,
  GraphPlanData,
  GraphClearedData,
} from "@/lib/sse_events";

type StrategyEventContext =
  & Pick<StrategyActions, "setStrategyMeta" | "addStep" | "setWdkInfo" | "addExecutedStrategy" | "clearStrategy">
  & Pick<StreamContext, "strategyIdAtStart" | "session" | "currentStrategy">
  & Pick<EventHelpers, "applyGraphSnapshot" | "getStrategy">;

/**
 * Resolve the target graph ID from event candidates, falling back to
 * `ctx.strategyIdAtStart`. Returns null when the event should be
 * skipped (no valid target, or target doesn't match the active strategy).
 */
function resolveTargetGraph(
  ctx: StrategyEventContext,
  ...candidates: (string | undefined | null)[]
): string | null {
  const id =
    candidates.find((c) => c != null && c !== "") ?? ctx.strategyIdAtStart ?? null;
  if (id == null || id === "") return null;
  if (
    ctx.strategyIdAtStart != null &&
    ctx.strategyIdAtStart !== "" &&
    id !== ctx.strategyIdAtStart
  )
    return null;
  return id;
}

export function handleStrategyUpdateEvent(
  ctx: StrategyEventContext,
  data: StrategyUpdateData,
) {
  const { step, graphId } = data;
  if (step == null) return;
  const targetGraphId = resolveTargetGraph(ctx, graphId, step.graphId);
  if (targetGraphId == null) return;

  ctx.session.captureUndoSnapshot(targetGraphId);
  if (step.name != null || step.description != null || step.recordType != null) {
    ctx.setStrategyMeta({
      ...(step.graphName != null
        ? { name: step.graphName }
        : step.name != null
          ? { name: step.name }
          : {}),
      ...(step.description != null ? { description: step.description } : {}),
      ...(step.recordType != null ? { recordType: step.recordType } : {}),
    });
  }
  const newStep: Step = {
    id: step.id,
    kind: (step.kind as string | null) ?? "search",
    displayName: step.displayName ?? step.kind ?? "Untitled step",
    isBuilt: step.isBuilt ?? false,
    isFiltered: step.isFiltered ?? false,
  };
  if (step.recordType != null) newStep.recordType = step.recordType;
  if (step.searchName != null) newStep.searchName = step.searchName;
  if (step.operator != null) newStep.operator = step.operator;
  if (step.primaryInputStepId != null)
    newStep.primaryInputStepId = step.primaryInputStepId;
  if (step.secondaryInputStepId != null)
    newStep.secondaryInputStepId = step.secondaryInputStepId;
  if (step.parameters != null)
    newStep.parameters = step.parameters as Record<string, unknown>;
  ctx.addStep(newStep);
  ctx.session.markSnapshotApplied();
}

export function handleGraphSnapshotEvent(
  ctx: StrategyEventContext,
  data: GraphSnapshotData,
) {
  const { graphSnapshot } = data;
  if (graphSnapshot) ctx.applyGraphSnapshot(graphSnapshot);
}

export function handleStrategyLinkEvent(ctx: StrategyEventContext, data: StrategyLinkData) {
  const { graphId, wdkStrategyId, wdkUrl, name, description, isSaved } = data;
  const targetGraphId = resolveTargetGraph(ctx, graphId);
  if (!targetGraphId) return;

  if (wdkStrategyId != null) ctx.setWdkInfo(wdkStrategyId, wdkUrl, name, description);
  ctx.setStrategyMeta({
    ...(name != null ? { name } : {}),
    ...(description != null ? { description } : {}),
    ...(isSaved != null ? { isSaved } : {}),
  });
  if (ctx.currentStrategy) {
    ctx.addExecutedStrategy({
      ...ctx.currentStrategy,
      ...(name != null ? { name } : {}),
      ...(description != null ? { description } : {}),
      ...(wdkStrategyId != null ? { wdkStrategyId } : {}),
      ...(wdkUrl != null ? { wdkUrl } : {}),
      ...(isSaved != null ? { isSaved } : {}),
      updatedAt: new Date().toISOString(),
    });
  } else {
    ctx
      .getStrategy(targetGraphId)
      .then((full) => ctx.addExecutedStrategy(full))
      .catch((err) =>
        console.error("[handleStrategyLinkEvent] Failed to fetch strategy:", err),
      );
  }
}

export function handleStrategyMetaEvent(ctx: StrategyEventContext, data: StrategyMetaData) {
  const { graphId, name, description, recordType, graphName } = data;
  if (resolveTargetGraph(ctx, graphId) == null) return;
  ctx.setStrategyMeta({
    ...(name != null ? { name } : graphName != null ? { name: graphName } : {}),
    ...(description != null ? { description } : {}),
    ...(recordType != null ? { recordType } : {}),
  });
}

export function handleGraphPlanEvent(ctx: StrategyEventContext, data: GraphPlanData) {
  const { graphId, name, description, recordType } = data;
  if (resolveTargetGraph(ctx, graphId) == null) return;
  // Update strategy metadata from the plan event.
  ctx.setStrategyMeta({
    ...(name != null ? { name } : {}),
    ...(description != null ? { description } : {}),
    ...(recordType != null ? { recordType } : {}),
  });
}

export function handleStrategyClearedEvent(
  ctx: StrategyEventContext,
  data: GraphClearedData,
) {
  const { graphId } = data;
  if (resolveTargetGraph(ctx, graphId) == null) return;
  ctx.clearStrategy();
}
