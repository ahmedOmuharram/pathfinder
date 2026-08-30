import { describe, expect, it } from "vitest";

import { toolUIState } from "./toolUIState";

describe("toolUIState", () => {
  it("marks a tool waiting on the user as approval-requested, not running", () => {
    expect(toolUIState("requires-action", undefined)).toBe("approval-requested");
  });

  it("maps the remaining assistant-ui statuses to tool call states", () => {
    expect(toolUIState("running", undefined)).toBe("input-available");
    expect(toolUIState("incomplete", undefined)).toBe("output-error");
    expect(toolUIState("complete", undefined)).toBe("input-streaming");
    expect(toolUIState("complete", { ok: true })).toBe("output-available");
  });
});
