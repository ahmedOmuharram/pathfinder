import type { UIMessage } from "ai";
import { describe, expect, it } from "vitest";

import { pendingPlanApprovalId } from "./RightRail";

function assistant(parts: UIMessage["parts"]): UIMessage {
  return { id: "m1", role: "assistant", parts };
}

describe("pendingPlanApprovalId", () => {
  it("returns the approval id when submit_plan awaits approval", () => {
    const messages = [
      assistant([
        {
          type: "tool-submit_plan_for_approval",
          toolCallId: "t1",
          state: "approval-requested",
          approval: { id: "appr-1" },
          input: { planId: "plan-1" },
        } as unknown as UIMessage["parts"][number],
      ]),
    ];
    expect(pendingPlanApprovalId(messages)).toBe("appr-1");
  });

  it("returns null when no submit_plan approval is pending", () => {
    const messages = [
      assistant([{ type: "text", text: "hello" } as UIMessage["parts"][number]]),
    ];
    expect(pendingPlanApprovalId(messages)).toBeNull();
  });

  it("ignores a submit_plan part that is already responded", () => {
    const messages = [
      assistant([
        {
          type: "tool-submit_plan_for_approval",
          toolCallId: "t1",
          state: "approval-responded",
          approval: { id: "appr-1" },
        } as unknown as UIMessage["parts"][number],
      ]),
    ];
    expect(pendingPlanApprovalId(messages)).toBeNull();
  });
});
