// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { getStrategyLifecycleDescriptor } from "./StrategyLifecycleBadge";

describe("getStrategyLifecycleDescriptor", () => {
  it("shows building during live scoping before any steps exist", () => {
    expect(
      getStrategyLifecycleDescriptor({
        stepCount: 0,
        wdkStrategyId: null,
        isSaved: false,
        isActiveStreaming: true,
        currentPhase: "scoping",
        phaseStatus: "started",
      }),
    ).toEqual({
      label: "Building • Scoping",
      tone: "bg-warning/10 text-warning",
    });
  });

  it("keeps saved as the base lifecycle label while streaming verification", () => {
    expect(
      getStrategyLifecycleDescriptor({
        stepCount: 3,
        wdkStrategyId: 42,
        isSaved: true,
        isActiveStreaming: true,
        currentPhase: "verification",
        phaseStatus: "started",
      }),
    ).toEqual({
      label: "Saved • Verification",
      tone: "bg-success/10 text-success",
    });
  });
});
