import type { StrategyListItem } from "@/features/sidebar/utils/strategyItems";

export type ConversationKind = "plan" | "strategy";

export interface ConversationItem {
  id: string;
  kind: ConversationKind;
  title: string;
  updatedAt: string;
  siteId?: string;
  stepCount?: number;
  strategyItem?: StrategyListItem;
}
