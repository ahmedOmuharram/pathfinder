import type { StrategyWithMeta } from "@/types/strategy";

export type StrategyListItem = {
  id: string;
  name: string;
  updatedAt: string;
  siteId?: string;
  wdkStrategyId?: number;
  source: "draft" | "synced";
  isRemote?: boolean;
  isInternal?: boolean;
};

export type WdkStrategySummary = {
  wdkStrategyId: number;
  name: string;
  siteId: string;
  wdkUrl?: string | null;
  rootStepId?: number | null;
  isSaved?: boolean | null;
  isInternal?: boolean;
};

/**
 * Build the StrategySidebar display list by merging:
 * - local app strategies (drafts and already-synced WDK strategies)
 * - remote WDK strategies that are not already present locally
 *
 * Internal WDK strategies are hidden.
 */
export function buildStrategySidebarItems(args: {
  local: StrategyWithMeta[];
  remote: WdkStrategySummary[];
  nowIso: () => string;
}): StrategyListItem[] {
  const { local, remote, nowIso } = args;

  const localItems: StrategyListItem[] = (local || []).map((item) => ({
    id: item.id,
    name: item.name,
    updatedAt: item.updatedAt,
    siteId: item.siteId,
    wdkStrategyId: item.wdkStrategyId,
    source: item.wdkStrategyId ? "synced" : "draft",
    isRemote: false,
  }));

  const localByWdkId = new Map(
    localItems.filter((i) => i.wdkStrategyId).map((i) => [i.wdkStrategyId, i]),
  );

  const remoteItems: StrategyListItem[] = (remote || [])
    .filter((item) => item?.wdkStrategyId)
    .map((item) => ({
      id: `wdk:${item.wdkStrategyId}`,
      name: item.name,
      updatedAt: nowIso(),
      siteId: item.siteId,
      wdkStrategyId: item.wdkStrategyId,
      source: "synced" as const,
      isRemote: !localByWdkId.has(item.wdkStrategyId),
      isInternal: Boolean(item.isInternal),
    }))
    // Hide internal WDK strategies (implementation details).
    .filter((item) => !item.isInternal)
    // Only show remote entries not already in local list.
    .filter((item) => item.isRemote);

  return [...localItems, ...remoteItems];
}
