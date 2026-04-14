import { describe, expect, it } from "vitest";

import type { PathfinderUIMessage } from "@pathfinder/shared";

import { groupMessagesByDay } from "./messageGroups";

function msg(id: string, createdAt?: string): PathfinderUIMessage {
  return {
    id,
    role: "assistant",
    parts: [],
    ...(createdAt !== undefined ? { metadata: { createdAt } } : {}),
  } as PathfinderUIMessage;
}

const NOW = new Date("2026-04-13T12:00:00Z");
const TODAY = "2026-04-13T08:00:00Z";
const YESTERDAY = "2026-04-12T23:00:00Z";
const LAST_WEEK = "2026-04-08T10:00:00Z";
const OLD = "2025-12-01T10:00:00Z";

describe("groupMessagesByDay", () => {
  it("returns empty groups for empty messages", () => {
    const result = groupMessagesByDay([], NOW);
    expect(result.groups).toEqual([]);
    expect(result.groupCounts).toEqual([]);
  });

  it("buckets consecutive same-day messages into one group", () => {
    const result = groupMessagesByDay(
      [msg("a", TODAY), msg("b", TODAY), msg("c", TODAY)],
      NOW,
    );
    expect(result.groups).toHaveLength(1);
    expect(result.groups[0]?.label).toBe("Today");
    expect(result.groupCounts).toEqual([3]);
  });

  it("splits into Today/Yesterday groups when dates differ", () => {
    const result = groupMessagesByDay(
      [msg("a", YESTERDAY), msg("b", YESTERDAY), msg("c", TODAY)],
      NOW,
    );
    expect(result.groups).toHaveLength(2);
    expect(result.groups[0]?.label).toBe("Yesterday");
    expect(result.groups[1]?.label).toBe("Today");
    expect(result.groupCounts).toEqual([2, 1]);
  });

  it("uses weekday name for messages in the last 6 days (not today/yesterday)", () => {
    const result = groupMessagesByDay([msg("a", LAST_WEEK)], NOW);
    expect(result.groups).toHaveLength(1);
    // Different locales format weekday names differently but it should not be
    // "Today" or "Yesterday" or a month-day.
    expect(result.groups[0]?.label).not.toBe("Today");
    expect(result.groups[0]?.label).not.toBe("Yesterday");
  });

  it("uses month-day for older same-year messages", () => {
    const OLDER_SAME_YEAR = "2026-01-15T10:00:00Z";
    const result = groupMessagesByDay([msg("a", OLDER_SAME_YEAR)], NOW);
    expect(result.groups[0]?.label).toMatch(/January|Jan/);
  });

  it("includes year for messages older than a year", () => {
    const result = groupMessagesByDay([msg("a", OLD)], NOW);
    expect(result.groups[0]?.label).toMatch(/2025/);
  });

  it("groups untimed leading messages together with the first timed day", () => {
    const result = groupMessagesByDay(
      [msg("a"), msg("b"), msg("c", TODAY)],
      NOW,
    );
    // A freshly-sent user message has no `createdAt` yet (server assigns it);
    // rather than showing "Recent" and then "Today", we label untimed
    // leading messages with the current day so the bubble lands with its
    // peers instead of a confusing separator.
    expect(result.groups.every((g) => g.label === "Today")).toBe(true);
    expect(result.groupCounts.reduce((a, b) => a + b, 0)).toBe(3);
  });

  it("inherits the prior day bucket for untimed messages between timed ones", () => {
    const result = groupMessagesByDay(
      [msg("a", TODAY), msg("b"), msg("c", TODAY)],
      NOW,
    );
    // All three share the Today bucket since untimed inherits.
    expect(result.groups).toHaveLength(1);
    expect(result.groups[0]?.label).toBe("Today");
    expect(result.groupCounts).toEqual([3]);
  });
});
