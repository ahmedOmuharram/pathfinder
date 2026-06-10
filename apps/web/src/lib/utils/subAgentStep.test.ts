import { describe, expect, it } from "vitest";

import type { DataSubAgentStepPayload } from "@pathfinder/shared";

import {
  collectSubAgentSteps,
  formatStepResult,
  mergeSubAgentSteps,
} from "./subAgentStep";

function step(p: Partial<DataSubAgentStepPayload>): DataSubAgentStepPayload {
  return {
    parentToolCallId: "parent",
    kind: "tool",
    state: "started",
    ...p,
  } as DataSubAgentStepPayload;
}

describe("formatStepResult", () => {
  it("extracts message + detail from a JSON error payload", () => {
    const raw =
      '{"ok": false, "code": "VALIDATION_ERROR", "message": "Invalid parameter value", "details": {"detail": "Parameter \'profileset_generic\' allows only one value."}}';
    const out = formatStepResult(raw);
    expect(out.tone).toBe("bad");
    expect(out.text).toContain("Invalid parameter value");
    expect(out.text).toContain("allows only one value");
  });

  it("still extracts the message from a TRUNCATED error payload", () => {
    const out = formatStepResult(
      '{"ok": false, "message": "Invalid parameter value", "details": {"det',
    );
    expect(out.tone).toBe("bad");
    expect(out.text).toBe("Invalid parameter value");
  });

  it("strips a coded error prefix", () => {
    const out = formatStepResult(
      "DISCOVERY_ERROR: PlannedParameter 'fold_change' is not valid",
    );
    expect(out.tone).toBe("bad");
    expect(out.text).toBe("PlannedParameter 'fold_change' is not valid");
  });

  it("flags a retry request", () => {
    expect(formatStepResult("retry requested").tone).toBe("bad");
  });

  it("passes plain prose through as neutral", () => {
    const out = formatStepResult("Recorded selected decision for GenesByX (0.85)");
    expect(out.tone).toBe("neutral");
    expect(out.text).toBe("Recorded selected decision for GenesByX (0.85)");
  });
});

describe("mergeSubAgentSteps", () => {
  it("merges started (args) + completed (result) into one tool item", () => {
    const items = mergeSubAgentSteps([
      step({
        kind: "tool",
        state: "started",
        toolCallId: "t1",
        toolName: "update_search_decision",
        args: { search_name: "GenesByX" },
      }),
      step({
        kind: "tool",
        state: "completed",
        toolCallId: "t1",
        toolName: "update_search_decision",
        resultSummary: "Recorded selected decision for GenesByX",
      }),
    ]);
    expect(items).toHaveLength(1);
    const only = items[0];
    expect(only?.type).toBe("tool");
    if (only?.type === "tool") {
      expect(only.state).toBe("completed");
      expect(only.args).toEqual({ search_name: "GenesByX" });
      expect(only.result).toBe("Recorded selected decision for GenesByX");
    }
  });

  it("keeps reasoning/text steps as ordered items", () => {
    const items = mergeSubAgentSteps([
      step({ kind: "reasoning", state: "completed", text: "thinking" }),
      step({
        kind: "tool",
        state: "started",
        toolCallId: "t1",
        toolName: "think",
      }),
    ]);
    expect(items.map((i) => i.type)).toEqual(["reasoning", "tool"]);
  });
});

describe("collectSubAgentSteps", () => {
  it("gathers persisted step parts by parentToolCallId across messages", () => {
    const messages = [
      {
        parts: [
          { type: "text" },
          {
            type: "data-sub-agent-step",
            data: step({ parentToolCallId: "call-a", toolName: "think" }),
          },
          {
            type: "data-sub-agent-step",
            data: step({ parentToolCallId: "call-b", toolName: "note" }),
          },
        ],
      },
      {
        parts: [
          {
            type: "data-sub-agent-step",
            data: step({ parentToolCallId: "call-a", toolName: "create_plan" }),
          },
        ],
      },
    ];
    const steps = collectSubAgentSteps(messages, "call-a");
    expect(steps.map((s) => s.toolName)).toEqual(["think", "create_plan"]);
  });

  it("returns nothing when no parts match", () => {
    expect(collectSubAgentSteps([{ parts: [{ type: "text" }] }], "x")).toEqual([]);
  });
});
