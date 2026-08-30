import { describe, expect, it } from "vitest";

import { humanizeToolName } from "./toolNames";

describe("humanizeToolName", () => {
  it("maps known tools to friendly labels", () => {
    expect(humanizeToolName("frame_problem")).toBe("Frame problem");
    expect(humanizeToolName("set_criterion")).toBe("Set criterion");
    expect(humanizeToolName("run_control_tests_on_step")).toBe("Run control tests");
    expect(humanizeToolName("build_strategy")).toBe("Build strategy");
    expect(humanizeToolName("compare_variants_scored")).toBe("Score variants");
    expect(humanizeToolName("build_control_set")).toBe("Build control set");
    expect(humanizeToolName("consult_user")).toBe("Ask the user");
  });

  it("names the enrichment job by the tool name its task puts on the wire", () => {
    expect(humanizeToolName("geneset_enrichment")).toBe("Gene set enrichment");
    expect(humanizeToolName("run_gene_set_enrichment")).toBe("Gene-set enrichment");
  });

  it("title-cases the deleted present_decision tool (no longer mapped)", () => {
    expect(humanizeToolName("present_decision")).toBe("Present decision");
  });

  it("title-cases unknown snake_case names", () => {
    expect(humanizeToolName("some_new_tool")).toBe("Some new tool");
  });

  it("strips a leading tool- prefix", () => {
    expect(humanizeToolName("tool-some_new_tool")).toBe("Some new tool");
  });
});
