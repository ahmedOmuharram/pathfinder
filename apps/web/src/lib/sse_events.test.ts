import { describe, expect, it } from "vitest";
import {
  parseChatSSEEvent,
  ToolCallStartDataSchema,
  ToolCallEndDataSchema,
  OptimizationProgressDataSchema,
  ModelSelectedDataSchema,
  ErrorDataSchema,
  StrategyUpdateDataSchema,
  WorkbenchGeneSetDataSchema,
  GraphPlanDataSchema,
  StrategyLinkDataSchema,
  StrategyMetaDataSchema,
  type RawSSEData,
  type ToolCallStartData,
} from "@/lib/sse_events";

describe("parseChatSSEEvent", () => {
  it("parses known event type with JSON payload", () => {
    const evt = parseChatSSEEvent({
      type: "assistant_message",
      data: JSON.stringify({ content: "hi" }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("assistant_message");
    if (evt!.type === "assistant_message") {
      expect(evt.data).toEqual({ content: "hi" });
    }
  });

  it("parses assistant_delta events", () => {
    const evt = parseChatSSEEvent({
      type: "assistant_delta",
      data: JSON.stringify({ messageId: "m1", delta: "hel" }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("assistant_delta");
    if (evt!.type === "assistant_delta") {
      expect(evt.data).toEqual({ messageId: "m1", delta: "hel" });
    }
  });

  it("parses model_selected events", () => {
    const pipeline = {
      discovery: { modelId: "anthropic/claude-sonnet-4-6", reasoningEffort: "medium" },
      planning: { modelId: "anthropic/claude-opus-4-6", reasoningEffort: "high" },
      execution: { modelId: "anthropic/claude-sonnet-4-6", reasoningEffort: "medium" },
      verification: { modelId: "anthropic/claude-opus-4-6", reasoningEffort: "high" },
    };
    const evt = parseChatSSEEvent({
      type: "model_selected",
      data: JSON.stringify({ pipeline }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("model_selected");
    if (evt!.type === "model_selected") {
      expect(evt.data.pipeline.planning.modelId).toBe("anthropic/claude-opus-4-6");
    }
  });

  it("parses graph_plan events", () => {
    const plan = { recordType: "transcript", root: { id: "s1" } };
    const evt = parseChatSSEEvent({
      type: "graph_plan",
      data: JSON.stringify({
        graphId: "g1",
        plan,
        name: "My plan",
        recordType: "transcript",
      }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("graph_plan");
    if (evt!.type === "graph_plan") {
      expect(evt.data.graphId).toBe("g1");
      expect(evt.data.plan).toEqual(plan);
      expect(evt.data.name).toBe("My plan");
      expect(evt.data.recordType).toBe("transcript");
    }
  });

  it("parses message_end events", () => {
    const evt = parseChatSSEEvent({
      type: "message_end",
      data: JSON.stringify({ done: true }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("message_end");
    if (evt!.type === "message_end") {
      expect(evt.data).toEqual({ done: true });
    }
  });

  it("returns unknown for forward-compatible events with object data", () => {
    const evt = parseChatSSEEvent({
      type: "future_event",
      data: JSON.stringify({ something: true }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("unknown");
    if (evt!.type === "unknown") {
      expect(evt.rawType).toBe("future_event");
    }
  });

  it("returns unknown with string data for non-JSON payloads", () => {
    const evt = parseChatSSEEvent({ type: "future_event", data: "x" });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("unknown");
    if (evt!.type === "unknown") {
      expect(evt.rawType).toBe("future_event");
      expect(evt.data).toBe("x");
    }
  });

  it("returns null for tool_call_start missing required fields", () => {
    const evt = parseChatSSEEvent({
      type: "tool_call_start",
      data: JSON.stringify({ name: "some_tool" }),
    });
    // Missing "id" field — known type but invalid data, skipped
    expect(evt).toBeNull();
  });

  it("returns null for error event missing error field", () => {
    const evt = parseChatSSEEvent({
      type: "error",
      data: JSON.stringify({ message: "something went wrong" }),
    });
    // Missing "error" field — known type but invalid data, skipped
    expect(evt).toBeNull();
  });

  it("parses strategy_update events with step data", () => {
    const evt = parseChatSSEEvent({
      type: "strategy_update",
      data: JSON.stringify({
        graphId: "g1",
        step: {
          id: "s1",
          displayName: "Gene by GO term",
          kind: "search",
          searchName: "GenesByGoTerm",
        },
      }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("strategy_update");
    if (evt!.type === "strategy_update") {
      expect(evt.data.graphId).toBe("g1");
      expect(evt.data.step?.id).toBe("s1");
    }
  });

  it("parses workbench_gene_set events", () => {
    const evt = parseChatSSEEvent({
      type: "workbench_gene_set",
      data: JSON.stringify({
        geneSet: {
          id: "gs1",
          name: "My genes",
          geneCount: 42,
          source: "manual",
          siteId: "plasmodb",
        },
      }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("workbench_gene_set");
    if (evt!.type === "workbench_gene_set") {
      expect(evt.data.geneSet?.id).toBe("gs1");
      expect(evt.data.geneSet?.geneCount).toBe(42);
    }
  });

  it("parses tool_call_start with all required fields", () => {
    const evt = parseChatSSEEvent({
      type: "tool_call_start",
      data: JSON.stringify({ id: "tc1", name: "search_genes", arguments: {} }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("tool_call_start");
    if (evt!.type === "tool_call_start") {
      expect(evt.data.id).toBe("tc1");
      expect(evt.data.name).toBe("search_genes");
    }
  });

  it("parses tool_call_end with all required fields", () => {
    const evt = parseChatSSEEvent({
      type: "tool_call_end",
      data: JSON.stringify({ id: "tc1", result: "found 5 genes" }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("tool_call_end");
    if (evt!.type === "tool_call_end") {
      expect(evt.data.id).toBe("tc1");
      expect(evt.data.result).toBe("found 5 genes");
    }
  });

  it("parses tool_call_end with missing result field (result is optional)", () => {
    const evt = parseChatSSEEvent({
      type: "tool_call_end",
      data: JSON.stringify({ id: "tc1" }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("tool_call_end");
    if (evt!.type === "tool_call_end") {
      expect(evt.data.id).toBe("tc1");
      expect(evt.data.result).toBeUndefined();
    }
  });

  it("returns null for optimization_progress missing optimizationId", () => {
    const evt = parseChatSSEEvent({
      type: "optimization_progress",
      data: JSON.stringify({ status: "running" }),
    });
    expect(evt).toBeNull();
  });

  it("returns null for model_selected missing modelId", () => {
    const evt = parseChatSSEEvent({
      type: "model_selected",
      data: JSON.stringify({ other: "field" }),
    });
    expect(evt).toBeNull();
  });

  it("returns null for model_selected with non-string modelId", () => {
    const evt = parseChatSSEEvent({
      type: "model_selected",
      data: JSON.stringify({ modelId: 123 }),
    });
    expect(evt).toBeNull();
  });

  it("returns null for tool_call_start with non-string id", () => {
    const evt = parseChatSSEEvent({
      type: "tool_call_start",
      data: JSON.stringify({ id: 123, name: "some_tool" }),
    });
    expect(evt).toBeNull();
  });

  it("returns null for error event with non-string error field", () => {
    const evt = parseChatSSEEvent({
      type: "error",
      data: JSON.stringify({ error: 42 }),
    });
    expect(evt).toBeNull();
  });

  it("parses optimization_progress with valid data", () => {
    const evt = parseChatSSEEvent({
      type: "optimization_progress",
      data: JSON.stringify({
        optimizationId: "opt1",
        status: "running",
        currentTrial: 5,
        totalTrials: 20,
      }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("optimization_progress");
  });

  it("parses error events with valid error field", () => {
    const evt = parseChatSSEEvent({
      type: "error",
      data: JSON.stringify({ error: "something broke" }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("error");
    if (evt!.type === "error") {
      expect(evt.data.error).toBe("something broke");
    }
  });

  it("preserves extra fields through passthrough schemas", () => {
    const evt = parseChatSSEEvent({
      type: "tool_call_start",
      data: JSON.stringify({
        id: "tc1",
        name: "search",
        arguments: {},
        extraField: "preserved",
      }),
    });
    expect(evt).not.toBeNull();
    if (evt!.type === "tool_call_start") {
      expect((evt.data as ToolCallStartData & RawSSEData)["extraField"]).toBe(
        "preserved",
      );
    }
  });

  // ── New tests for Zod-validated event types ─────────────────────────

  it("returns null for strategy_update with invalid step (missing id)", () => {
    const evt = parseChatSSEEvent({
      type: "strategy_update",
      data: JSON.stringify({
        graphId: "g1",
        step: { displayName: "Gene search" },
      }),
    });
    expect(evt).toBeNull();
  });

  it("parses strategy_update without step (empty update)", () => {
    const evt = parseChatSSEEvent({
      type: "strategy_update",
      data: JSON.stringify({ graphId: "g1" }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("strategy_update");
    if (evt!.type === "strategy_update") {
      expect(evt.data.graphId).toBe("g1");
      expect(evt.data.step).toBeUndefined();
    }
  });

  it("parses workbench_gene_set with partial geneSet (all fields optional)", () => {
    const evt = parseChatSSEEvent({
      type: "workbench_gene_set",
      data: JSON.stringify({
        geneSet: { id: "gs1", geneCount: 5, source: "manual", siteId: "plasmodb" },
      }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("workbench_gene_set");
    if (evt!.type === "workbench_gene_set") {
      expect(evt.data.geneSet?.id).toBe("gs1");
    }
  });

  it("parses workbench_gene_set without geneSet field (optional)", () => {
    const evt = parseChatSSEEvent({
      type: "workbench_gene_set",
      data: JSON.stringify({}),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("workbench_gene_set");
    if (evt!.type === "workbench_gene_set") {
      expect(evt.data.geneSet).toBeUndefined();
    }
  });

  it("parses strategy_link events via Zod", () => {
    const evt = parseChatSSEEvent({
      type: "strategy_link",
      data: JSON.stringify({
        graphId: "g1",
        wdkStrategyId: 42,
        wdkUrl: "https://plasmodb.org/strategy/42",
        name: "My Strategy",
      }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("strategy_link");
    if (evt!.type === "strategy_link") {
      expect(evt.data.wdkStrategyId).toBe(42);
      expect(evt.data.wdkUrl).toBe("https://plasmodb.org/strategy/42");
    }
  });

  it("returns null for strategy_link with non-number wdkStrategyId", () => {
    const evt = parseChatSSEEvent({
      type: "strategy_link",
      data: JSON.stringify({
        graphId: "g1",
        wdkStrategyId: "not-a-number",
      }),
    });
    expect(evt).toBeNull();
  });

  it("parses strategy_meta events via Zod", () => {
    const evt = parseChatSSEEvent({
      type: "strategy_meta",
      data: JSON.stringify({
        graphId: "g1",
        name: "My Strategy",
        recordType: null,
      }),
    });
    expect(evt).not.toBeNull();
    expect(evt!.type).toBe("strategy_meta");
    if (evt!.type === "strategy_meta") {
      expect(evt.data.name).toBe("My Strategy");
      expect(evt.data.recordType).toBeNull();
    }
  });

  it("returns null for strategy_meta with non-string graphId", () => {
    const evt = parseChatSSEEvent({
      type: "strategy_meta",
      data: JSON.stringify({ graphId: 123 }),
    });
    expect(evt).toBeNull();
  });
});

/* ── Zod schema unit tests ─────────────────────────────────────────── */

describe("SSE event data Zod schemas", () => {
  describe("ToolCallStartDataSchema", () => {
    it("accepts valid data with required fields", () => {
      const result = ToolCallStartDataSchema.safeParse({
        id: "tc1",
        name: "search_genes",
      });
      expect(result.success).toBe(true);
    });

    it("accepts data with optional arguments", () => {
      const result = ToolCallStartDataSchema.safeParse({
        id: "tc1",
        name: "search_genes",
        arguments: { query: "kinase" },
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.arguments).toEqual({ query: "kinase" });
      }
    });

    it("rejects data missing id", () => {
      const result = ToolCallStartDataSchema.safeParse({ name: "tool" });
      expect(result.success).toBe(false);
    });

    it("rejects data missing name", () => {
      const result = ToolCallStartDataSchema.safeParse({ id: "tc1" });
      expect(result.success).toBe(false);
    });

    it("rejects data with non-string id", () => {
      const result = ToolCallStartDataSchema.safeParse({
        id: 123,
        name: "tool",
      });
      expect(result.success).toBe(false);
    });

    it("passes through extra fields", () => {
      const result = ToolCallStartDataSchema.safeParse({
        id: "tc1",
        name: "tool",
        extra: true,
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect((result.data as RawSSEData)["extra"]).toBe(true);
      }
    });
  });

  describe("ToolCallEndDataSchema", () => {
    it("accepts valid data", () => {
      const result = ToolCallEndDataSchema.safeParse({
        id: "tc1",
        result: "found genes",
      });
      expect(result.success).toBe(true);
    });

    it("rejects data missing id", () => {
      const result = ToolCallEndDataSchema.safeParse({
        result: "found genes",
      });
      expect(result.success).toBe(false);
    });

    it("accepts data with missing result (result is optional)", () => {
      const result = ToolCallEndDataSchema.safeParse({ id: "tc1" });
      expect(result.success).toBe(true);
    });
  });

  describe("OptimizationProgressDataSchema", () => {
    it("accepts minimal valid data", () => {
      const result = OptimizationProgressDataSchema.safeParse({
        optimizationId: "opt1",
        status: "running",
      });
      expect(result.success).toBe(true);
    });

    it("accepts full data with all optional fields", () => {
      const result = OptimizationProgressDataSchema.safeParse({
        optimizationId: "opt1",
        status: "completed",
        searchName: "GenesByGoTerm",
        recordType: "transcript",
        budget: 100,
        objective: "maximize_recall",
        currentTrial: 50,
        totalTrials: 100,
        trial: {
          trialNumber: 50,
          parameters: { threshold: 0.5 },
          score: 0.9,
          recall: 0.85,
          falsePositiveRate: 0.1,
          estimatedSize: 100,
          positiveHits: 85,
          negativeHits: 10,
          totalPositives: 100,
          totalNegatives: 100,
        },
      });
      expect(result.success).toBe(true);
    });

    it("rejects data missing optimizationId", () => {
      const result = OptimizationProgressDataSchema.safeParse({
        status: "running",
      });
      expect(result.success).toBe(false);
    });

    it("rejects data missing status", () => {
      const result = OptimizationProgressDataSchema.safeParse({
        optimizationId: "opt1",
      });
      expect(result.success).toBe(false);
    });

    it("rejects invalid status value", () => {
      const result = OptimizationProgressDataSchema.safeParse({
        optimizationId: "opt1",
        status: "invalid_status",
      });
      expect(result.success).toBe(false);
    });
  });

  describe("ModelSelectedDataSchema", () => {
    const validPipeline = {
      pipeline: {
        discovery: { modelId: "anthropic/claude-sonnet-4-6", reasoningEffort: "medium" },
        planning: { modelId: "anthropic/claude-opus-4-6", reasoningEffort: "high" },
        execution: { modelId: "anthropic/claude-sonnet-4-6", reasoningEffort: "medium" },
        verification: { modelId: "anthropic/claude-opus-4-6", reasoningEffort: "high" },
      },
    };

    it("accepts valid pipeline data", () => {
      const result = ModelSelectedDataSchema.safeParse(validPipeline);
      expect(result.success).toBe(true);
    });

    it("rejects data missing pipeline", () => {
      const result = ModelSelectedDataSchema.safeParse({});
      expect(result.success).toBe(false);
    });

    it("rejects pipeline missing a phase", () => {
      const result = ModelSelectedDataSchema.safeParse({
        pipeline: {
          discovery: { modelId: "x", reasoningEffort: "medium" },
          planning: { modelId: "x", reasoningEffort: "high" },
          execution: { modelId: "x", reasoningEffort: "medium" },
          // verification missing
        },
      });
      expect(result.success).toBe(false);
    });
  });

  describe("ErrorDataSchema", () => {
    it("accepts valid data", () => {
      const result = ErrorDataSchema.safeParse({ error: "something broke" });
      expect(result.success).toBe(true);
    });

    it("rejects data missing error field", () => {
      const result = ErrorDataSchema.safeParse({ message: "wrong field" });
      expect(result.success).toBe(false);
    });

    it("rejects non-string error field", () => {
      const result = ErrorDataSchema.safeParse({ error: 42 });
      expect(result.success).toBe(false);
    });
  });

  describe("StrategyUpdateDataSchema", () => {
    it("accepts empty update (no step)", () => {
      const result = StrategyUpdateDataSchema.safeParse({ graphId: "g1" });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.graphId).toBe("g1");
        expect(result.data.step).toBeUndefined();
      }
    });

    it("accepts update with valid step", () => {
      const result = StrategyUpdateDataSchema.safeParse({
        graphId: "g1",
        step: {
          id: "s1",
          displayName: "Gene search",
          searchName: "GeneByTextSearch",
          kind: "search",
        },
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.step?.id).toBe("s1");
        expect(result.data.step?.displayName).toBe("Gene search");
      }
    });

    it("rejects step missing id", () => {
      const result = StrategyUpdateDataSchema.safeParse({
        step: { displayName: "Gene search" },
      });
      expect(result.success).toBe(false);
    });

    it("passes through extra fields on step", () => {
      const result = StrategyUpdateDataSchema.safeParse({
        step: {
          id: "s1",
          displayName: "Gene search",
          futureField: 99,
        },
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect((result.data.step as RawSSEData)["futureField"]).toBe(99);
      }
    });
  });

  describe("WorkbenchGeneSetDataSchema", () => {
    it("accepts empty data (no geneSet)", () => {
      const result = WorkbenchGeneSetDataSchema.safeParse({});
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.geneSet).toBeUndefined();
      }
    });

    it("accepts valid geneSet", () => {
      const result = WorkbenchGeneSetDataSchema.safeParse({
        geneSet: {
          id: "gs1",
          name: "My genes",
          geneCount: 42,
          source: "manual",
          siteId: "plasmodb",
        },
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.geneSet?.id).toBe("gs1");
        expect(result.data.geneSet?.geneCount).toBe(42);
      }
    });

    it("accepts geneSet with partial fields (all optional)", () => {
      const result = WorkbenchGeneSetDataSchema.safeParse({
        geneSet: { id: "gs1" },
      });
      expect(result.success).toBe(true);
    });

    it("rejects geneSet with non-number geneCount", () => {
      const result = WorkbenchGeneSetDataSchema.safeParse({
        geneSet: {
          id: "gs1",
          name: "My genes",
          geneCount: "forty-two",
          source: "manual",
          siteId: "plasmodb",
        },
      });
      expect(result.success).toBe(false);
    });
  });

  describe("GraphPlanDataSchema", () => {
    it("accepts valid plan data", () => {
      const result = GraphPlanDataSchema.safeParse({
        graphId: "g1",
        plan: { recordType: "gene", root: { searchName: "GenesByText" } },
        name: "My plan",
        recordType: "gene",
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.graphId).toBe("g1");
        expect(result.data.name).toBe("My plan");
      }
    });

    it("accepts plan as any value (plan is z.unknown)", () => {
      const result = GraphPlanDataSchema.safeParse({
        plan: "string-plan",
      });
      expect(result.success).toBe(true);
    });

    it("accepts null plan", () => {
      const result = GraphPlanDataSchema.safeParse({
        plan: null,
      });
      expect(result.success).toBe(true);
    });

    it("rejects non-string graphId", () => {
      const result = GraphPlanDataSchema.safeParse({
        graphId: 123,
        plan: {},
      });
      expect(result.success).toBe(false);
    });
  });

  describe("StrategyLinkDataSchema", () => {
    it("accepts valid link data", () => {
      const result = StrategyLinkDataSchema.safeParse({
        graphId: "g1",
        wdkStrategyId: 42,
        wdkUrl: "https://plasmodb.org/strategy/42",
        name: "My Strategy",
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.wdkStrategyId).toBe(42);
      }
    });

    it("accepts empty data (all optional)", () => {
      const result = StrategyLinkDataSchema.safeParse({});
      expect(result.success).toBe(true);
    });

    it("rejects non-number wdkStrategyId", () => {
      const result = StrategyLinkDataSchema.safeParse({
        wdkStrategyId: "not-a-number",
      });
      expect(result.success).toBe(false);
    });

    it("rejects non-string graphId", () => {
      const result = StrategyLinkDataSchema.safeParse({
        graphId: 123,
      });
      expect(result.success).toBe(false);
    });
  });

  describe("StrategyMetaDataSchema", () => {
    it("accepts valid meta data", () => {
      const result = StrategyMetaDataSchema.safeParse({
        graphId: "g1",
        name: "My Strategy",
        recordType: "gene",
      });
      expect(result.success).toBe(true);
    });

    it("accepts null recordType", () => {
      const result = StrategyMetaDataSchema.safeParse({
        recordType: null,
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.recordType).toBeNull();
      }
    });

    it("accepts empty data (all optional)", () => {
      const result = StrategyMetaDataSchema.safeParse({});
      expect(result.success).toBe(true);
    });

    it("rejects non-string graphId", () => {
      const result = StrategyMetaDataSchema.safeParse({
        graphId: 123,
      });
      expect(result.success).toBe(false);
    });
  });
});
