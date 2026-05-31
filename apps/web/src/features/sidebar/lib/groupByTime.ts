import { isToday, isYesterday, subWeeks, subMonths } from "date-fns";

import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";

export interface TimeGroup {
  label: string;
  items: ConversationItem[];
}

export function groupConversationsByTime(items: ConversationItem[]): TimeGroup[] {
  const now = new Date();
  const oneWeekAgo = subWeeks(now, 1);
  const oneMonthAgo = subMonths(now, 1);

  const saved: ConversationItem[] = [];
  const today: ConversationItem[] = [];
  const yesterday: ConversationItem[] = [];
  const lastWeek: ConversationItem[] = [];
  const lastMonth: ConversationItem[] = [];
  const older: ConversationItem[] = [];

  for (const item of items) {
    if (item.isSaved) {
      saved.push(item);
      continue;
    }
    const date = new Date(item.updatedAt);
    if (isToday(date)) today.push(item);
    else if (isYesterday(date)) yesterday.push(item);
    else if (date > oneWeekAgo) lastWeek.push(item);
    else if (date > oneMonthAgo) lastMonth.push(item);
    else older.push(item);
  }

  const groups: TimeGroup[] = [];
  if (saved.length > 0) groups.push({ label: "Saved", items: saved });
  if (today.length > 0) groups.push({ label: "Today", items: today });
  if (yesterday.length > 0) groups.push({ label: "Yesterday", items: yesterday });
  if (lastWeek.length > 0) groups.push({ label: "Last 7 days", items: lastWeek });
  if (lastMonth.length > 0) groups.push({ label: "Last 30 days", items: lastMonth });
  if (older.length > 0) groups.push({ label: "Older", items: older });
  return groups;
}
