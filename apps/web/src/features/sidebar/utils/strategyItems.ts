/**
 * Sidebar strategy list item type.
 *
 * After the WDK draft/saved migration, all strategies are auto-synced
 * with WDK. Visual state is derived from ``wdkStrategyId`` and ``isSaved``:
 *
 * - No ``wdkStrategyId`` -> "not synced" / building indicator
 * - ``wdkStrategyId`` + ``isSaved=false`` -> "Draft" badge
 * - ``wdkStrategyId`` + ``isSaved=true`` -> "Saved" badge
 */
export type StrategyListItem = {
  id: string;
  name: string;
  updatedAt: string;
  siteId?: string;
  wdkStrategyId?: number;
  isSaved: boolean;
};
