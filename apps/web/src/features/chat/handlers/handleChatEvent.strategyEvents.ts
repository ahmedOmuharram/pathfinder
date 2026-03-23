import type { Step } from "@pathfinder/shared";
import type { ChatEventContext } from "./handleChatEvent.types";
import type {
  StrategyUpdateData,
  GraphSnapshotData,
  StrategyLinkData,
  StrategyMetaData,
  GraphPlanData,
  ExecutorBuildRequestData,
  GraphClearedData,
} from "@/lib/sse_events";

/**
 * Resolve the target graph ID from event candidates, falling back to
 * `ctx.strategyIdAtStart`. Returns null when the event should be
 * skipped (no valid target, or target doesn't match the active strategy).
 */
function resolveTargetGraph(
  ctx: ChatEventContext,
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
  ctx: ChatEventContext,
  data: StrategyUpdateData,
) {
  const { step, graphId } = data;
  if (step == null) return;
  const targetGraphId = resolveTargetGraph(ctx, graphId, step.graphId as string | null);
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
    id: step.stepId,
    kind: (step.kind as string | null) ?? "search",
    displayName:
      (step.displayName as string | undefined) ?? step.kind ?? "Untitled step",
    isBuilt: false,
    isFiltered: false,
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
  ctx: ChatEventContext,
  data: GraphSnapshotData,
) {
  const { graphSnapshot } = data;
  if (graphSnapshot) ctx.applyGraphSnapshot(graphSnapshot);
}

export function handleStrategyLinkEvent(ctx: ChatEventContext, data: StrategyLinkData) {
  const { graphId, wdkStrategyId, wdkUrl, name, description } = data;
  const targetGraphId = resolveTargetGraph(ctx, graphId);
  if (!targetGraphId) return;

  if (wdkStrategyId != null) ctx.setWdkInfo(wdkStrategyId, wdkUrl, name, description);
  ctx.setStrategyMeta({
    ...(name != null ? { name } : {}),
    ...(description != null ? { description } : {}),
  });
  if (ctx.currentStrategy) {
    ctx.addExecutedStrategy({
      ...ctx.currentStrategy,
      ...(name != null ? { name } : {}),
      ...(description != null ? { description } : {}),
      ...(wdkStrategyId != null ? { wdkStrategyId } : {}),
      ...(wdkUrl != null ? { wdkUrl } : {}),
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

export function handleStrategyMetaEvent(ctx: ChatEventContext, data: StrategyMetaData) {
  const { graphId, name, description, recordType, graphName } = data;
  if (resolveTargetGraph(ctx, graphId) == null) return;
  ctx.setStrategyMeta({
    ...(name != null ? { name } : graphName != null ? { name: graphName } : {}),
    ...(description != null ? { description } : {}),
    ...(recordType != null ? { recordType } : {}),
  });
}

export function handleGraphPlanEvent(ctx: ChatEventContext, data: GraphPlanData) {
  const { graphId, name, description, recordType } = data;
  if (resolveTargetGraph(ctx, graphId) == null) return;
  // Update strategy metadata from the plan event.
  ctx.setStrategyMeta({
    ...(name != null ? { name } : {}),
    ...(description != null ? { description } : {}),
    ...(recordType != null ? { recordType } : {}),
  });
}

export function handleExecutorBuildRequestEvent(
  _ctx: ChatEventContext,
  _data: ExecutorBuildRequestData,
) {
  // executor_build_request is an informational event emitted when the backend
  // begins a build request.  No frontend action is needed — the subsequent
  // strategy_link / graph_plan events carry the actual results.
}

export function handleStrategyClearedEvent(
  ctx: ChatEventContext,
  data: GraphClearedData,
) {
  const { graphId } = data;
  if (resolveTargetGraph(ctx, graphId) == null) return;
  ctx.clearStrategy();
}
