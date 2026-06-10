import { describe, expect, it } from "vitest";

import { humanizeToolName } from "./toolNames";

describe("humanizeToolName", () => {
  it("maps known tools to friendly labels", () => {
    expect(humanizeToolName("create_plan")).toBe("Build plan");
    expect(humanizeToolName("update_search_decision")).toBe("Search decision");
    expect(humanizeToolName("run_control_tests_on_step")).toBe("Run control tests");
    expect(humanizeToolName("submit_plan_for_approval")).toBe("Submit plan");
  });

  it("title-cases unknown snake_case names", () => {
    expect(humanizeToolName("some_new_tool")).toBe("Some new tool");
  });

  it("strips a leading tool- prefix", () => {
    expect(humanizeToolName("tool-some_new_tool")).toBe("Some new tool");
  });
});
