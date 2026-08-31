import { describe, expect, it } from "vitest";
import { PHASE_DESCRIPTIONS, PHASE_LABELS, PHASE_ROLES } from "./phaseRoles";

const INTERNAL = /\b(EDA|WDK|FRAME|BUILD|VERIFY|Frame|Ledger|Lead|sub-agent)\b/;

describe("phase role metadata", () => {
  it("has a non-empty label and description for every role", () => {
    expect(PHASE_ROLES).toContain("lead");
    for (const role of PHASE_ROLES) {
      expect(PHASE_LABELS[role]).toBe(
        {
          lead: "Assistant",
          frame: "Planning",
          execution: "Building",
          verification: "Checking",
        }[role],
      );
      expect(PHASE_DESCRIPTIONS[role].length).toBeGreaterThan(0);
    }
  });

  it("labels every phase the wire carries, including the recorded alias", () => {
    expect(PHASE_LABELS).toEqual({
      lead: "Assistant",
      frame: "Planning",
      build: "Building",
      execution: "Building",
      verification: "Checking",
      recover_failed_steps: "Repairing",
    });
  });

  it("names no internal word in a label or a description", () => {
    for (const text of [
      ...Object.values(PHASE_LABELS),
      ...Object.values(PHASE_DESCRIPTIONS),
    ]) {
      expect(INTERNAL.test(text), text).toBe(false);
    }
  });
});
