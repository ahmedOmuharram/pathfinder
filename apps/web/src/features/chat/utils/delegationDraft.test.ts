import { describe, expect, it } from "vitest";
import {
  buildDelegationExecutorMessage,
  getDelegationDraft,
} from "@/features/chat/utils/delegationDraft";

describe("delegationDraft", () => {
  it("returns null when no delegation_draft artifact", () => {
    expect(getDelegationDraft([] as any)).toBeNull();
  });

  it("extracts goal/plan from record parameters", () => {
    const artifacts = [
      {
        id: "delegation_draft",
        parameters: { delegationGoal: "G", delegationPlan: { a: 1 } },
      },
    ];
    expect(getDelegationDraft(artifacts as any)).toEqual({ goal: "G", plan: { a: 1 } });
  });

  it("ignores non-record parameters and non-string goal", () => {
    const artifacts = [
      { id: "delegation_draft", parameters: "nope" },
      { id: "delegation_draft", parameters: { delegationGoal: 123 } },
    ];
    expect(getDelegationDraft(artifacts.slice(0, 1) as any)).toEqual({
      goal: undefined,
      plan: undefined,
    });
    expect(getDelegationDraft(artifacts.slice(1, 2) as any)).toEqual({
      goal: undefined,
      plan: undefined,
    });
  });

  it("builds executor message with JSON fenced block", () => {
    const msg = buildDelegationExecutorMessage({ goal: "Goal", plan: { x: 1 } });
    expect(msg).toMatch(/delegate_strategy_subtasks/);
    expect(msg).toMatch(/```/);
    expect(msg).toMatch(/"x": 1/);
  });
});
