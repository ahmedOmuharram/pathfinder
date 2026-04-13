/**
 * Groups a flat list of `PathfinderUIMessage`s into day-buckets for rendering
 * sticky day dividers inside `GroupedVirtuoso`.
 *
 * Uses `metadata.createdAt` (ISO string) when present. Consecutive messages
 * with no timestamp inherit the preceding day's bucket; leading untimed
 * messages fall into a "Recent" bucket. The output preserves the original
 * message order — `groupCounts` and `groupContent` pair with it 1:1.
 */

import type { PathfinderUIMessage } from "@pathfinder/shared";

export interface DayGroup {
  label: string;
  count: number;
}

export interface DayGroupedMessages {
  groups: DayGroup[];
  groupCounts: number[];
}

const MS_PER_DAY = 86_400_000;
const RECENT_LABEL = "Recent";

export function groupMessagesByDay(
  messages: readonly PathfinderUIMessage[],
  now: Date = new Date(),
): DayGroupedMessages {
  if (messages.length === 0) {
    return { groups: [], groupCounts: [] };
  }

  const groups: DayGroup[] = [];
  let currentLabel: string | null = null;

  for (const message of messages) {
    const derived = dayLabelFor(message.metadata?.createdAt, now);
    const label: string = derived ?? currentLabel ?? RECENT_LABEL;
    const lastGroup = groups[groups.length - 1];
    if (lastGroup !== undefined && label === currentLabel) {
      lastGroup.count += 1;
    } else {
      groups.push({ label, count: 1 });
      currentLabel = label;
    }
  }

  return {
    groups,
    groupCounts: groups.map((g) => g.count),
  };
}

function dayLabelFor(iso: string | undefined, now: Date): string | null {
  if (iso === undefined || iso.length === 0) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;

  const today = startOfDay(now).getTime();
  const target = startOfDay(date).getTime();
  const diffDays = Math.round((today - target) / MS_PER_DAY);

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays > 0 && diffDays < 7) {
    return new Intl.DateTimeFormat(undefined, { weekday: "long" }).format(date);
  }
  if (date.getFullYear() === now.getFullYear()) {
    return new Intl.DateTimeFormat(undefined, {
      month: "long",
      day: "numeric",
    }).format(date);
  }
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

function startOfDay(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}
