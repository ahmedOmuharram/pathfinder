/**
 * Regression tests for `ModelSelectedDataSchema` validation and the
 * silent-drop behavior in `parseChatSSEEvent` when a backend payload
 * does not match the strict 5-phase `PipelinePhaseSchema`.
 *
 * Today the schema requires every phase (scoping/discovery/planning/
 * execution/verification).  If the backend serializes with
 * `exclude_none=True` and a phase becomes `null` → omitted, parsing
 * fails silently (only a `console.warn`).  This is the mechanism
 * that produces the intermittent "missing model name/icon" UI bug.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import {
  ModelSelectedDataSchema,
  parseChatSSEEvent,
} from "@/lib/sse_events";

const FULL_PIPELINE = {
  scoping: { modelId: "anthropic/claude-sonnet-4-6", reasoningEffort: "medium" },
  discovery: {
    modelId: "anthropic/claude-sonnet-4-6",
    reasoningEffort: "medium",
  },
  planning: { modelId: "anthropic/claude-opus-4-6", reasoningEffort: "high" },
  execution: {
    modelId: "anthropic/claude-sonnet-4-6",
    reasoningEffort: "medium",
  },
  verification: {
    modelId: "anthropic/claude-opus-4-6",
    reasoningEffort: "high",
  },
};

describe("ModelSelectedDataSchema", () => {
  it("parses a complete 5-phase pipeline", () => {
    const result = ModelSelectedDataSchema.safeParse({ pipeline: FULL_PIPELINE });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toEqual({ pipeline: FULL_PIPELINE });
    }
  });

  it("FAILS when a pipeline phase is missing (only 4 phases)", () => {
    // Backend accidentally omitted `verification` (e.g. exclude_none).
    const payload = {
      pipeline: {
        scoping: FULL_PIPELINE.scoping,
        discovery: FULL_PIPELINE.discovery,
        planning: FULL_PIPELINE.planning,
        execution: FULL_PIPELINE.execution,
        // verification intentionally missing
      },
    };

    const result = ModelSelectedDataSchema.safeParse(payload);
    expect(result.success).toBe(false);
    if (!result.success) {
      // Issue should be "invalid_type" or similar for the missing phase.
      const issuePaths = result.error.issues.map((i) => i.path.join("."));
      expect(issuePaths).toContain("pipeline.verification");
    }
  });

  it("FAILS when a phase has a non-string modelId (e.g. null from exclude_none)", () => {
    const payload = {
      pipeline: {
        ...FULL_PIPELINE,
        planning: { modelId: null, reasoningEffort: "high" },
      },
    };

    const result = ModelSelectedDataSchema.safeParse(payload);
    expect(result.success).toBe(false);
  });

  it("FAILS when `pipeline` itself is missing", () => {
    const result = ModelSelectedDataSchema.safeParse({ other: "field" });
    expect(result.success).toBe(false);
  });
});

describe("parseChatSSEEvent silently drops invalid model_selected", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns null AND warns console when model_selected payload is incomplete", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    const evt = parseChatSSEEvent({
      type: "model_selected",
      data: JSON.stringify({
        pipeline: {
          scoping: FULL_PIPELINE.scoping,
          discovery: FULL_PIPELINE.discovery,
          planning: FULL_PIPELINE.planning,
          execution: FULL_PIPELINE.execution,
          // verification missing — intentional
        },
      }),
    });

    // Known type + invalid data → null (silent drop).
    expect(evt).toBeNull();

    // console.warn was called with the failing event type.
    expect(warnSpy).toHaveBeenCalled();
    const calls = warnSpy.mock.calls;
    const firstMsg = calls[0]?.[0];
    expect(typeof firstMsg).toBe("string");
    expect(firstMsg as string).toMatch(/model_selected/);
  });

  it("returns a valid ChatSSEEvent when all 5 phases are present", () => {
    const evt = parseChatSSEEvent({
      type: "model_selected",
      data: JSON.stringify({ pipeline: FULL_PIPELINE }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("model_selected");
    if (evt!.type === "model_selected") {
      expect(evt.data.pipeline.planning.modelId).toBe(
        "anthropic/claude-opus-4-6",
      );
      expect(evt.data.pipeline.verification.modelId).toBe(
        "anthropic/claude-opus-4-6",
      );
    }
  });

  it("returns null when pipeline.planning.reasoningEffort is missing", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    const evt = parseChatSSEEvent({
      type: "model_selected",
      data: JSON.stringify({
        pipeline: {
          ...FULL_PIPELINE,
          planning: { modelId: "gpt-4" }, // reasoningEffort missing
        },
      }),
    });

    expect(evt).toBeNull();
    expect(warnSpy).toHaveBeenCalled();
  });
});
