import { describe, expect, it } from "vitest";
import { mergeMessages } from "./mergeMessages";
import { parseToolArguments } from "./parseToolArguments";
import { extractDelegateSummaries } from "./extractDelegateSummaries";

describe("features/chat/utils", () => {
  it("mergeMessages only accepts incoming when at least as complete", () => {
    const a = { role: "user", content: "a", timestamp: "t1" } as any;
    const b = { role: "user", content: "b", timestamp: "t2" } as any;
    expect(mergeMessages([a], [])).toEqual([a]);
    expect(mergeMessages([a], [a])).toHaveLength(1);
    expect(mergeMessages([a, b], [a])).toHaveLength(2);
    expect(mergeMessages([a], [a, b])).toHaveLength(2);
  });

  it("mergeMessages preserves local optimizationProgress when server returns null", () => {
    const localOpt = {
      optimizationId: "o1",
      status: "completed" as const,
      currentTrial: 5,
      totalTrials: 5,
    };
    const local = [
      {
        role: "assistant",
        content: "done",
        optimizationProgress: localOpt,
        timestamp: "t1",
      },
    ] as any;
    const incoming = [
      {
        role: "assistant",
        content: "done",
        optimizationProgress: null,
        timestamp: "t1",
      },
    ] as any;
    const result = mergeMessages(local, incoming);
    expect(result[0].optimizationProgress).toEqual(localOpt);
  });

  it("mergeMessages preserves local optimizationProgress when server returns undefined", () => {
    const localOpt = {
      optimizationId: "o1",
      status: "completed" as const,
      currentTrial: 5,
      totalTrials: 5,
    };
    const local = [
      {
        role: "assistant",
        content: "done",
        optimizationProgress: localOpt,
        timestamp: "t1",
      },
    ] as any;
    const incoming = [{ role: "assistant", content: "done", timestamp: "t1" }] as any;
    const result = mergeMessages(local, incoming);
    expect(result[0].optimizationProgress).toEqual(localOpt);
  });

  it("mergeMessages uses server optimizationProgress when it has data", () => {
    const serverOpt = {
      optimizationId: "o2",
      status: "completed" as const,
      currentTrial: 10,
      totalTrials: 10,
    };
    const local = [{ role: "assistant", content: "done", timestamp: "t1" }] as any;
    const incoming = [
      {
        role: "assistant",
        content: "done",
        optimizationProgress: serverOpt,
        timestamp: "t1",
      },
    ] as any;
    const result = mergeMessages(local, incoming);
    expect(result[0].optimizationProgress).toEqual(serverOpt);
  });

  it("parseToolArguments handles objects and JSON strings safely", () => {
    expect(parseToolArguments(null)).toEqual({});
    expect(parseToolArguments({ a: 1 })).toEqual({ a: 1 });
    expect(parseToolArguments("[1,2,3]")).toEqual({});
    expect(parseToolArguments('{"a":1}')).toEqual({ a: 1 });
    expect(parseToolArguments("{bad json")).toEqual({});
  });

  it("extractDelegateSummaries parses delegate_strategy_subtasks results", () => {
    const toolCalls = [
      { id: "x", name: "other", arguments: {}, result: "{}" },
      {
        id: "d1",
        name: "delegate_strategy_subtasks",
        arguments: {},
        result: JSON.stringify({
          results: [
            {
              task: "t",
              steps: [{ stepId: "s1", displayName: "S1", recordType: "gene" }],
              notes: "n",
            },
          ],
          rejected: [{ task: "r", error: "e", details: "d" }],
        }),
      },
    ] as any;

    const res = extractDelegateSummaries(toolCalls);
    expect(res.summaries).toHaveLength(1);
    expect(res.summaries[0]?.task).toBe("t");
    expect(res.rejected).toHaveLength(1);
    expect(res.rejected[0]?.error).toBe("e");
  });
});
