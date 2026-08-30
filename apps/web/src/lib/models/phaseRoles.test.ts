import { describe, expect, it } from "vitest";
import { PHASE_DESCRIPTIONS, PHASE_LABELS, PHASE_ROLES } from "./phaseRoles";

describe("phase role metadata", () => {
  it("has a non-empty label and description for every role", () => {
    expect(PHASE_ROLES).toContain("lead");
    for (const role of PHASE_ROLES) {
      expect(PHASE_LABELS[role]).toBe(
        {
          lead: "Lead",
          frame: "Frame",
          execution: "Build",
          verification: "Verification",
        }[role],
      );
      expect(PHASE_DESCRIPTIONS[role].length).toBeGreaterThan(0);
    }
  });

  it("labels every phase the wire carries, including the recorded alias", () => {
    expect(PHASE_LABELS).toEqual({
      lead: "Lead",
      frame: "Frame",
      build: "Build",
      execution: "Build",
      verification: "Verification",
      recover_failed_steps: "Recovery",
    });
  });
});
