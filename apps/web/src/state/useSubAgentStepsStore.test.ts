// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import type { DataSubAgentStepPayload } from "@pathfinder/shared";

import { useSubAgentStepsStore } from "./useSubAgentStepsStore";

function makeStep(parentToolCallId: string, label: string): DataSubAgentStepPayload {
  return { parentToolCallId, label } as unknown as DataSubAgentStepPayload;
}

beforeEach(() => {
  useSubAgentStepsStore.getState().reset();
});

describe("useSubAgentStepsStore", () => {
  it("groups appended steps by their parent tool-call id", () => {
    const s = useSubAgentStepsStore.getState();
    s.appendStep(makeStep("call-1", "a"));
    s.appendStep(makeStep("call-1", "b"));
    s.appendStep(makeStep("call-2", "c"));
    const { byParent } = useSubAgentStepsStore.getState();
    expect(byParent["call-1"]).toHaveLength(2);
    expect(byParent["call-2"]).toHaveLength(1);
  });

  it("reset clears all grouped steps", () => {
    const s = useSubAgentStepsStore.getState();
    s.appendStep(makeStep("call-1", "a"));
    s.reset();
    expect(useSubAgentStepsStore.getState().byParent).toEqual({});
  });
});
