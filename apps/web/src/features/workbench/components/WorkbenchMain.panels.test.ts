import { describe, expect, it } from "vitest";

import { WORKBENCH_PANELS } from "./WorkbenchMain";
import { BatchPanel, BenchmarkPanel, EvaluatePanel } from "./panels";

// Regression: the experiment-running panels (Evaluate/Batch/Benchmark) were
// exported but never mounted in WorkbenchMain, so no experiment could be run
// through the UI and every lastExperiment-gated panel stayed dead.
describe("WorkbenchMain panel composition", () => {
  it("mounts the experiment-running panels", () => {
    expect(WORKBENCH_PANELS).toContain(EvaluatePanel);
    expect(WORKBENCH_PANELS).toContain(BatchPanel);
    expect(WORKBENCH_PANELS).toContain(BenchmarkPanel);
  });

  it("mounts a non-trivial set of panels", () => {
    expect(WORKBENCH_PANELS.length).toBeGreaterThanOrEqual(9);
  });
});
