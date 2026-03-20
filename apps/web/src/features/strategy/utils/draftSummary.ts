import type { Strategy } from "@pathfinder/shared";
import { DEFAULT_STREAM_NAME } from "@pathfinder/shared";

export function buildDraftStrategySummary(args: {
  id: string;
  siteId: string;
  nowIso: () => string;
}): Strategy {
  const { id, siteId, nowIso } = args;
  const ts = nowIso();
  return {
    id,
    name: DEFAULT_STREAM_NAME,
    title: DEFAULT_STREAM_NAME,
    siteId,
    recordType: null,
    stepCount: 0,
    isSaved: false,
    createdAt: ts,
    updatedAt: ts,
    steps: [],
    rootStepId: null,
  };
}
