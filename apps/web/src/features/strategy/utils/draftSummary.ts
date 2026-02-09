import type { StrategySummary } from "@pathfinder/shared";

export function buildDraftStrategySummary(args: {
  id: string;
  siteId: string;
  nowIso: () => string;
}): StrategySummary {
  const { id, siteId, nowIso } = args;
  const ts = nowIso();
  return {
    id,
    name: "Draft Strategy",
    title: "Draft Strategy",
    siteId,
    recordType: null,
    stepCount: 0,
    resultCount: undefined,
    wdkStrategyId: undefined,
    createdAt: ts,
    updatedAt: ts,
  };
}
