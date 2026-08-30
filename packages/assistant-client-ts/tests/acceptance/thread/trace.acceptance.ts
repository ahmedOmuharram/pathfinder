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

import { TURN } from "./traceTurn";
import { api, at, client, runs, sdkParts } from "./traceClient";
describe.skipIf(client === null)("buildTrace over the recorded turn", () => {
  it("yields exactly one run, because an empty run is never emitted", () => {
    const traces = runs(api().reduceTurn(TURN).parts);

    expect(traces).toHaveLength(1);
  });

  it("counts seven rows, three figures, and reports the turn still running", () => {
    const run = at(runs(api().reduceTurn(TURN).parts), 0);

    expect(run.rowCount).toBe(7);
    expect(run.running).toBe(true);
    expect(run.figures).toHaveLength(3);
    expect(run.figures.map((figure) => figure.type)).toEqual([
      "data-eda.analysis-state",
      "data-eda.subset-preview",
      "data-eda.viz",
    ]);
  });

  it("groups the rows lead, sa_1, lead", () => {
    const run = at(runs(api().reduceTurn(TURN).parts), 0);

    expect(run.groups.map((group) => group.key)).toEqual(["lead", "sa_1", "lead"]);
    expect(run.groups.map((group) => group.phase)).toEqual(["lead", "frame", "lead"]);
    expect(run.groups.map((group) => group.rows.length)).toEqual([2, 2, 3]);
  });

  it("carries the sub-agent group's usage and its merged step rows", () => {
    const group = at(at(runs(api().reduceTurn(TURN).parts), 0).groups, 1);

    expect(group.tokens).toBe(12300);
    expect(group.costUsd).toBe("0.004");
    expect(group.state).toBe("completed");
    expect(group.rows.map((row) => row.toolName)).toEqual([
      "search_for_searches",
      "set_criterion",
    ]);
    expect(group.rows.map((row) => row.summary)).toEqual([
      "12 searches",
      "c1 set to GenesByText",
    ]);
  });

  it("names every lead row and the summary its tool wrote", () => {
    const run = at(runs(api().reduceTurn(TURN).parts), 0);
    const rows = run.groups.flatMap((group) => group.rows);

    expect(rows.map((row) => row.toolName)).toEqual([
      "search_eda_studies",
      "open_eda_analysis",
      "search_for_searches",
      "set_criterion",
      "preview_eda_subset",
      "run_control_tests_on_step",
      "optimize_search_parameters",
    ]);
    expect(rows.map((row) => row.summary)).toEqual([
      "3 studies matched heat shock",
      "Opened Febrile samples on DS_e973eadd57",
      "12 searches",
      "c1 set to GenesByText",
      "6 of 12 Sample",
      "8 of 10 positive controls recovered",
      null,
    ]);
  });

  it("leaves the suspended call awaiting approval with no summary", () => {
    const run = at(runs(api().reduceTurn(TURN).parts), 0);
    const rows = run.groups.flatMap((group) => group.rows);
    const row = at(rows, 6);

    expect(row.toolCallId).toBe("call_5");
    expect(row.status).toBe("awaiting-approval");
    expect(row.summary).toBeNull();
  });

  it("yields the same trace from the client reducer and from the AI SDK path", () => {
    const reduced = runs(api().reduceTurn(TURN).parts);
    const live = runs(sdkParts());

    expect(live).toEqual(reduced);
    expect(at(live, 0).rowCount).toBe(7);
  });
});
