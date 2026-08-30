/**
 * Frozen acceptance: `buildTrace`, the one place the trace grouping rule lives.
 *
 * No-edit rule: implementers may not touch `tests/acceptance/**`. A test that
 * is genuinely wrong is escalated to the session lead, who is the only party
 * that edits this suite.
 *
 * The turn below is the same chunk sequence as
 * `apps/web/src/acceptance/thread/recordedTurn.json`, inlined because an
 * acceptance module carries its own fixtures. The module skips until batch 1
 * exports `buildTrace` and folds the summary.
 */
import { describe, expect, it } from "vitest";

import { at, client, runs, tool } from "./traceClient";
describe.skipIf(client === null)("buildTrace run boundaries", () => {
  it("splits two tool parts on the text part between them", () => {
    const traces = runs([
      tool("search_eda_studies", "call_1"),
      { type: "text", text: "One moment.", state: "done" },
      tool("preview_eda_subset", "call_3"),
    ]);

    expect(traces).toHaveLength(2);
    expect(at(traces, 0).rowCount).toBe(1);
    expect(at(traces, 1).rowCount).toBe(1);
  });

  it("keeps two tool parts together across an empty reasoning part", () => {
    const traces = runs([
      tool("search_eda_studies", "call_1"),
      { type: "reasoning", text: "", state: "done" },
      tool("preview_eda_subset", "call_3"),
    ]);

    expect(traces).toHaveLength(1);
    expect(at(traces, 0).rowCount).toBe(2);
  });

  it("keeps two tool parts together across a reasoning part with content", () => {
    const traces = runs([
      tool("search_eda_studies", "call_1"),
      { type: "reasoning", text: "weighing the filter", state: "done" },
      tool("preview_eda_subset", "call_3"),
    ]);

    expect(traces).toHaveLength(1);
    expect(at(traces, 0).rowCount).toBe(2);
  });

  it("keeps two tool parts together across an empty text part", () => {
    const traces = runs([
      tool("search_eda_studies", "call_1"),
      { type: "text", text: "", state: "done" },
      tool("preview_eda_subset", "call_3"),
    ]);

    expect(traces).toHaveLength(1);
    expect(at(traces, 0).rowCount).toBe(2);
  });

  it("keeps two tool parts together across a step-start part", () => {
    const traces = runs([
      tool("search_eda_studies", "call_1"),
      { type: "step-start" },
      tool("preview_eda_subset", "call_3"),
    ]);

    expect(traces).toHaveLength(1);
    expect(at(traces, 0).rowCount).toBe(2);
  });

  it("keeps two tool parts together across a data-turn-status part", () => {
    const traces = runs([
      tool("search_eda_studies", "call_1"),
      { type: "data-turn-status", data: { label: "Thinking...", waitingOnLlm: true } },
      tool("preview_eda_subset", "call_3"),
    ]);

    expect(traces).toHaveLength(1);
    expect(at(traces, 0).rowCount).toBe(2);
  });

  it("does not hoist a turn failure notice into the run's figures", () => {
    const traces = runs([
      tool("search_eda_studies", "call_1"),
      { type: "data-turn-failed", data: { errorText: "The turn ran out of budget." } },
    ]);

    expect(traces).toHaveLength(1);
    expect(at(traces, 0).rowCount).toBe(1);
    expect(at(traces, 0).figures).toHaveLength(0);
  });

  it("does not hoist a stopped notice into the run's figures", () => {
    const traces = runs([
      tool("search_eda_studies", "call_1"),
      { type: "data-turn-stopped", data: { reason: "The user stopped this turn." } },
    ]);

    expect(traces).toHaveLength(1);
    expect(at(traces, 0).rowCount).toBe(1);
    expect(at(traces, 0).figures).toHaveLength(0);
  });
});
