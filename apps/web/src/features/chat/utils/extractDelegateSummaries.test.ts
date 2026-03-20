import { describe, expect, it } from "vitest";
import type { ToolCall } from "@pathfinder/shared";
import {
  extractDelegateSummaries,
  type DelegateSummary,
  type RejectedDelegateSummary,
} from "./extractDelegateSummaries";

function makeDelegateToolCall(result: string, overrides?: Partial<ToolCall>): ToolCall {
  return {
    id: overrides?.id ?? "tc-delegate",
    name: "delegate_strategy_subtasks",
    arguments: overrides?.arguments ?? {},
    result,
  };
}

function makeOtherToolCall(name: string): ToolCall {
  return {
    id: "tc-other",
    name,
    arguments: {},
    result: '{"data": "irrelevant"}',
  };
}

describe("extractDelegateSummaries", () => {
  // ─── Empty / no delegate calls ─────────────────────────────────────

  it("returns empty arrays for empty toolCalls", () => {
    const { summaries, rejected } = extractDelegateSummaries([]);
    expect(summaries).toEqual([]);
    expect(rejected).toEqual([]);
  });

  it("returns empty arrays when no tool calls match delegate_strategy_subtasks", () => {
    const { summaries, rejected } = extractDelegateSummaries([
      makeOtherToolCall("some_tool"),
      makeOtherToolCall("another_tool"),
    ]);
    expect(summaries).toEqual([]);
    expect(rejected).toEqual([]);
  });

  // ─── Valid results extraction ──────────────────────────────────────

  it("extracts a single summary from results", () => {
    const payload = JSON.stringify({
      results: [
        {
          task: "Find genes",
          steps: [
            {
              stepId: "s1",
              displayName: "Gene Search",
              searchName: "GeneByName",
              recordType: "gene",
            },
          ],
          notes: "Found 42 genes",
        },
      ],
    });
    const { summaries, rejected } = extractDelegateSummaries([
      makeDelegateToolCall(payload),
    ]);
    expect(summaries).toHaveLength(1);
    expect(summaries[0]).toEqual({
      task: "Find genes",
      steps: [
        {
          stepId: "s1",
          displayName: "Gene Search",
          searchName: "GeneByName",
          recordType: "gene",
        },
      ],
      notes: "Found 42 genes",
    } satisfies DelegateSummary);
    expect(rejected).toEqual([]);
  });

  it("extracts multiple summaries from results array", () => {
    const payload = JSON.stringify({
      results: [
        { task: "Task A", steps: [], notes: "note A" },
        { task: "Task B", steps: [{ stepId: "s2" }] },
      ],
    });
    const { summaries } = extractDelegateSummaries([makeDelegateToolCall(payload)]);
    expect(summaries).toHaveLength(2);
    expect(summaries[0]!.task).toBe("Task A");
    expect(summaries[0]!.notes).toBe("note A");
    expect(summaries[1]!.task).toBe("Task B");
    expect(summaries[1]!.notes).toBeUndefined();
  });

  // ─── Rejected entries ─────────────────────────────────────────────

  it("extracts rejected entries", () => {
    const payload = JSON.stringify({
      rejected: [
        {
          task: "Bad task",
          error: "invalid_search",
          details: "Search not found",
        },
      ],
    });
    const { summaries, rejected } = extractDelegateSummaries([
      makeDelegateToolCall(payload),
    ]);
    expect(summaries).toEqual([]);
    expect(rejected).toHaveLength(1);
    expect(rejected[0]).toEqual({
      task: "Bad task",
      error: "invalid_search",
      details: "Search not found",
    } satisfies RejectedDelegateSummary);
  });

  it("extracts both results and rejected from the same call", () => {
    const payload = JSON.stringify({
      results: [{ task: "Good task", steps: [] }],
      rejected: [{ task: "Bad task", error: "failed" }],
    });
    const { summaries, rejected } = extractDelegateSummaries([
      makeDelegateToolCall(payload),
    ]);
    expect(summaries).toHaveLength(1);
    expect(rejected).toHaveLength(1);
  });

  // ─── Multiple delegate tool calls ─────────────────────────────────

  it("aggregates summaries across multiple delegate tool calls", () => {
    const payload1 = JSON.stringify({
      results: [{ task: "Task 1", steps: [] }],
    });
    const payload2 = JSON.stringify({
      results: [{ task: "Task 2", steps: [] }],
      rejected: [{ error: "err" }],
    });
    const { summaries, rejected } = extractDelegateSummaries([
      makeDelegateToolCall(payload1, { id: "tc-1" }),
      makeDelegateToolCall(payload2, { id: "tc-2" }),
    ]);
    expect(summaries).toHaveLength(2);
    expect(summaries[0]!.task).toBe("Task 1");
    expect(summaries[1]!.task).toBe("Task 2");
    expect(rejected).toHaveLength(1);
  });

  // ─── Mixed tool calls (delegate + other) ──────────────────────────

  it("ignores non-delegate tool calls while extracting delegate ones", () => {
    const payload = JSON.stringify({
      results: [{ task: "My task", steps: [{ stepId: "s1" }] }],
    });
    const { summaries } = extractDelegateSummaries([
      makeOtherToolCall("build_strategy"),
      makeDelegateToolCall(payload),
      makeOtherToolCall("get_results"),
    ]);
    expect(summaries).toHaveLength(1);
    expect(summaries[0]!.task).toBe("My task");
  });

  // ─── Defaults for missing fields ──────────────────────────────────

  it("defaults task to empty string when missing", () => {
    const payload = JSON.stringify({
      results: [{ steps: [{ stepId: "s1" }] }],
    });
    const { summaries } = extractDelegateSummaries([makeDelegateToolCall(payload)]);
    expect(summaries[0]!.task).toBe("");
  });

  it("defaults steps to empty array when missing", () => {
    const payload = JSON.stringify({
      results: [{ task: "No steps" }],
    });
    const { summaries } = extractDelegateSummaries([makeDelegateToolCall(payload)]);
    expect(summaries[0]!.steps).toEqual([]);
  });

  // ─── Invalid / malformed results ──────────────────────────────────

  it("skips delegate calls with null result", () => {
    const tc: ToolCall = {
      id: "tc-null",
      name: "delegate_strategy_subtasks",
      arguments: {},
      result: null,
    };
    const { summaries, rejected } = extractDelegateSummaries([tc]);
    expect(summaries).toEqual([]);
    expect(rejected).toEqual([]);
  });

  it("skips delegate calls with invalid JSON result", () => {
    const { summaries, rejected } = extractDelegateSummaries([
      makeDelegateToolCall("{not valid json}"),
    ]);
    expect(summaries).toEqual([]);
    expect(rejected).toEqual([]);
  });

  it("skips delegate calls with non-object JSON result", () => {
    const { summaries, rejected } = extractDelegateSummaries([
      makeDelegateToolCall("[1,2,3]"),
    ]);
    expect(summaries).toEqual([]);
    expect(rejected).toEqual([]);
  });

  it("skips delegate calls with string JSON result", () => {
    const { summaries, rejected } = extractDelegateSummaries([
      makeDelegateToolCall('"just a string"'),
    ]);
    expect(summaries).toEqual([]);
    expect(rejected).toEqual([]);
  });

  // ─── passthrough: extra fields are tolerated ───────────────────────

  it("tolerates extra fields in the payload via passthrough", () => {
    const payload = JSON.stringify({
      results: [{ task: "T", steps: [] }],
      extraField: "ignored",
      metadata: { foo: "bar" },
    });
    const { summaries } = extractDelegateSummaries([makeDelegateToolCall(payload)]);
    expect(summaries).toHaveLength(1);
    expect(summaries[0]!.task).toBe("T");
  });

  // ─── Empty results / rejected arrays ──────────────────────────────

  it("handles empty results and rejected arrays", () => {
    const payload = JSON.stringify({ results: [], rejected: [] });
    const { summaries, rejected } = extractDelegateSummaries([
      makeDelegateToolCall(payload),
    ]);
    expect(summaries).toEqual([]);
    expect(rejected).toEqual([]);
  });

  it("handles payload with only results key missing", () => {
    const payload = JSON.stringify({
      rejected: [{ task: "Bad" }],
    });
    const { summaries, rejected } = extractDelegateSummaries([
      makeDelegateToolCall(payload),
    ]);
    expect(summaries).toEqual([]);
    expect(rejected).toHaveLength(1);
  });

  it("handles payload with only rejected key missing", () => {
    const payload = JSON.stringify({
      results: [{ task: "Good", steps: [] }],
    });
    const { summaries, rejected } = extractDelegateSummaries([
      makeDelegateToolCall(payload),
    ]);
    expect(summaries).toHaveLength(1);
    expect(rejected).toEqual([]);
  });

  // ─── Partial step objects ──────────────────────────────────────────

  it("handles steps with only some optional fields", () => {
    const payload = JSON.stringify({
      results: [
        {
          task: "Partial steps",
          steps: [
            { stepId: "s1" },
            { displayName: "Step 2" },
            { searchName: "Q1", recordType: "gene" },
            {},
          ],
        },
      ],
    });
    const { summaries } = extractDelegateSummaries([makeDelegateToolCall(payload)]);
    expect(summaries[0]!.steps).toHaveLength(4);
    expect(summaries[0]!.steps[0]!).toEqual({ stepId: "s1" });
    expect(summaries[0]!.steps[3]!).toEqual({});
  });

  // ─── Rejected with partial fields ─────────────────────────────────

  it("handles rejected entries with only some fields", () => {
    const payload = JSON.stringify({
      rejected: [{ error: "failed" }, { task: "T" }, {}],
    });
    const { rejected } = extractDelegateSummaries([makeDelegateToolCall(payload)]);
    expect(rejected).toHaveLength(3);
    expect(rejected[0]).toEqual({ error: "failed" });
    expect(rejected[1]).toEqual({ task: "T" });
    expect(rejected[2]).toEqual({});
  });
});
