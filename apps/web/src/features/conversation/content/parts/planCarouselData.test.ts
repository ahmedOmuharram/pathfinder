import type { UIMessage } from "ai";
import { describe, expect, it } from "vitest";

import {
  carouselPhase,
  findPending,
  findConsultRecap,
  findPendingConsult,
  latestPlan,
  planForCarousel,
} from "./planCarouselData";

function assistant(parts: unknown[]): UIMessage {
  return { id: "m1", role: "assistant", parts } as unknown as UIMessage;
}

describe("latestPlan", () => {
  it("returns the last plan artifact in the message", () => {
    const message = assistant([
      { type: "data-plan-artifact", data: { planId: "p1", steps: [], rationale: "" } },
      {
        type: "data-plan-artifact",
        data: { planId: "p2", steps: [{ searchName: "X" }], rationale: "r" },
      },
    ]);
    expect(latestPlan(message)?.planId).toBe("p2");
  });

  it("returns null when there is no plan artifact", () => {
    expect(latestPlan(assistant([{ type: "text", text: "hi" }]))).toBeNull();
  });
});

describe("planForCarousel", () => {
  const planMsg = {
    id: "a1",
    role: "assistant",
    parts: [
      {
        type: "data-plan-artifact",
        data: { planId: "p1", steps: [{ searchName: "X" }], rationale: "r" },
      },
      {
        type: "tool-submit_plan_for_approval",
        state: "approval-responded",
        approval: { id: "old" },
      },
    ],
  } as unknown as UIMessage;
  const resubmitMsg = {
    id: "a2",
    role: "assistant",
    parts: [
      {
        type: "tool-submit_plan_for_approval",
        state: "approval-requested",
        approval: { id: "new" },
        input: {},
      },
    ],
  } as unknown as UIMessage;

  it("uses the plan inline in the message when present", () => {
    expect(planForCarousel(planMsg, [planMsg])?.planId).toBe("p1");
  });

  it("falls back to the latest thread plan when a re-submit carries no artifact", () => {
    // The re-submit message has a pending approval but no plan-artifact.
    expect(planForCarousel(resubmitMsg, [planMsg, resubmitMsg])?.planId).toBe("p1");
  });

  it("returns null when there is neither an inline plan nor a pending approval", () => {
    const plain = {
      id: "a3",
      role: "assistant",
      parts: [{ type: "text", text: "hi" }],
    } as unknown as UIMessage;
    expect(planForCarousel(plain, [plain])).toBeNull();
  });
});

describe("findPending", () => {
  it("returns the pending submit approval", () => {
    const message = assistant([
      {
        type: "tool-submit_plan_for_approval",
        state: "approval-requested",
        approval: { id: "appr-1" },
        input: { planId: "p2" },
      },
    ]);
    const pending = findPending(message);
    expect(pending?.approvalId).toBe("appr-1");
    expect(pending?.planId).toBe("p2");
  });

  it("returns null when the approval is already responded", () => {
    const message = assistant([
      {
        type: "tool-submit_plan_for_approval",
        state: "approval-responded",
        approval: { id: "appr-1" },
      },
    ]);
    expect(findPending(message)).toBeNull();
  });
});

describe("carouselPhase", () => {
  it("is streaming while the assistant turn is still running", () => {
    expect(
      carouselPhase({ statusType: "running", hasPending: true, submitted: false }),
    ).toBe("streaming");
  });

  it("is interactive when ready with a pending approval", () => {
    expect(
      carouselPhase({ statusType: "complete", hasPending: true, submitted: false }),
    ).toBe("interactive");
  });

  it("is readonly once submitted, even if a stale pending lingers", () => {
    expect(
      carouselPhase({ statusType: "complete", hasPending: true, submitted: true }),
    ).toBe("readonly");
  });

  it("is readonly when the plan is built but never gated for approval", () => {
    expect(
      carouselPhase({ statusType: "complete", hasPending: false, submitted: false }),
    ).toBe("readonly");
  });
});

describe("findPendingConsult", () => {
  it("reads questions off a pending consult_user approval part", () => {
    const message = assistant([
      {
        type: "tool-consult_user",
        state: "approval-requested",
        approval: { id: "appr-9" },
        input: {
          questions: [
            {
              id: "q1",
              prompt: "Fold-change threshold?",
              kind: "single_choice",
              options: [{ label: "2-fold", recommended: true }, { label: "5-fold" }],
              context: "Higher is stricter.",
              allowNotes: true,
            },
          ],
        },
      },
    ]);
    const pending = findPendingConsult(message);
    expect(pending?.approvalId).toBe("appr-9");
    expect(pending?.questions).toHaveLength(1);
    expect(pending?.questions[0]?.prompt).toBe("Fold-change threshold?");
    expect(pending?.questions[0]?.options[0]?.recommended).toBe(true);
  });

  it("returns null when there is no pending consult", () => {
    expect(findPendingConsult(assistant([{ type: "text", text: "hi" }]))).toBeNull();
  });
});

describe("findConsultRecap", () => {
  it("reads questions + chosen answers from a resolved consult tool part", () => {
    const message = assistant([
      {
        type: "tool-consult_user",
        state: "output-available",
        input: {
          questions: [
            { id: "q1", prompt: "Threshold?", options: [{ label: "2-fold" }] },
          ],
        },
        output: [
          {
            questionId: "q1",
            prompt: "Threshold?",
            chosenLabels: ["2-fold"],
            note: "",
          },
        ],
      },
    ]);
    const recap = findConsultRecap(message);
    expect(recap?.questions[0]?.prompt).toBe("Threshold?");
    expect(recap?.answers[0]?.chosenLabels).toEqual(["2-fold"]);
  });

  it("returns null when the consult is still pending", () => {
    const message = assistant([
      {
        type: "tool-consult_user",
        state: "approval-requested",
        approval: { id: "a" },
        input: { questions: [] },
      },
    ]);
    expect(findConsultRecap(message)).toBeNull();
  });
});
