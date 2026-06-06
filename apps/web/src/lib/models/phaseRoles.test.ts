import { describe, expect, it } from "vitest";
import { PHASE_DESCRIPTIONS, PHASE_LABELS, PHASE_ROLES } from "./phaseRoles";

describe("phase role metadata", () => {
  it("has a non-empty label and description for every role", () => {
    expect(PHASE_ROLES).toContain("lead");
    for (const role of PHASE_ROLES) {
      expect(PHASE_LABELS[role]).toBeTruthy();
      expect(PHASE_DESCRIPTIONS[role]).toBeTruthy();
    }
  });
});
