import type { PlanArtifact, PlanSlotForm } from "@pathfinder/shared";
import type { JsonValue } from "@pathfinder/shared/generated/types/JsonValue";
import type { UIMessage } from "ai";

import type { PendingApprovalInfo } from "../../rail/planPanelActions";

export type Slide = { kind: "slots"; slots: PlanSlotForm[] };

function strField(o: Record<string, JsonValue>, key: string): string {
  const v = o[key];
  return typeof v === "string" ? v : "";
}

function strList(o: Record<string, JsonValue>, key: string): string[] {
  const v = o[key];
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}

function isPartType(part: { type: string; name?: string }, kind: string): boolean {
  return part.type === `data-${kind}` || (part.type === "data" && part.name === kind);
}

// The plan + carousel is one inline block with three visual phases.
//  - "streaming": the assistant turn is still being written → shimmer.
//  - "interactive": plan is ready and a submit-approval is pending → the
//    user answers questions and approves.
//  - "readonly": the turn is done (submitted, or built with no pending gate)
//    → plan + questions shown statically, scrolling up with the chat.
export type CarouselPhase = "streaming" | "interactive" | "readonly";

export function carouselPhase(args: {
  statusType: string | undefined;
  hasPending: boolean;
  submitted: boolean;
}): CarouselPhase {
  if (args.statusType === "running") return "streaming";
  if (!args.submitted && args.hasPending) return "interactive";
  return "readonly";
}

export function latestPlan(message: UIMessage): PlanArtifact | null {
  let found: PlanArtifact | null = null;
  for (const part of message.parts) {
    if (isPartType(part, "plan-artifact")) {
      const data = (part as { data?: PlanArtifact }).data;
      if (data != null) found = data;
    }
  }
  return found;
}

export function planForCarousel(
  message: UIMessage,
  allMessages: readonly UIMessage[],
): PlanArtifact | null {
  const inline = latestPlan(message);
  if (inline !== null) return inline;
  // A re-submitted plan (after request-changes) carries a fresh approval but
  // no new plan-artifact, so resolve the plan from the thread.
  if (findPending(message) !== null) return latestPlanAcross(allMessages);
  return null;
}

export function latestPlanAcross(messages: readonly UIMessage[]): PlanArtifact | null {
  let found: PlanArtifact | null = null;
  for (const message of messages) {
    if (message.role !== "assistant") continue;
    const plan = latestPlan(message);
    if (plan !== null) found = plan;
  }
  return found;
}

export function isSubmitResolved(message: UIMessage): boolean {
  for (const part of message.parts) {
    if (part.type !== "tool-submit_plan_for_approval" || !("state" in part)) continue;
    if (part.state === "approval-responded" || part.state === "output-available") {
      return true;
    }
  }
  return false;
}

export interface ConsultOptionView {
  label: string;
  description: string;
  recommended: boolean;
}

export interface ConsultQuestionView {
  id: string;
  prompt: string;
  kind: "single_choice" | "multi_choice" | "free_text";
  options: ConsultOptionView[];
  context: string;
  allowNotes: boolean;
}

export interface PendingConsult {
  approvalId: string;
  questions: ConsultQuestionView[];
  sourceMessage: UIMessage;
}

function parseConsultQuestion(o: Record<string, JsonValue>): ConsultQuestionView {
  const rawOptions = Array.isArray(o["options"]) ? o["options"] : [];
  const kind = o["kind"];
  return {
    id: strField(o, "id"),
    prompt: strField(o, "prompt"),
    kind: kind === "multi_choice" || kind === "free_text" ? kind : "single_choice",
    context: strField(o, "context"),
    allowNotes: o["allowNotes"] !== false,
    options: rawOptions
      .filter(
        (x): x is Record<string, JsonValue> => typeof x === "object" && x !== null,
      )
      .map((x) => ({
        label: strField(x, "label"),
        description: strField(x, "description"),
        recommended: x["recommended"] === true,
      })),
  };
}

export interface ConsultAnswerView {
  questionId: string;
  prompt: string;
  chosenLabels: string[];
  note: string;
}

export interface ConsultRecap {
  questions: ConsultQuestionView[];
  answers: ConsultAnswerView[];
}

function parseConsultAnswer(o: Record<string, JsonValue>): ConsultAnswerView {
  return {
    questionId: strField(o, "questionId"),
    prompt: strField(o, "prompt"),
    chosenLabels: strList(o, "chosenLabels"),
    note: strField(o, "note"),
  };
}

export function findConsultRecap(message: UIMessage): ConsultRecap | null {
  for (const part of message.parts) {
    if (
      part.type !== "tool-consult_user" ||
      !("state" in part) ||
      part.state !== "output-available"
    ) {
      continue;
    }
    const output = "output" in part ? part.output : undefined;
    const rawAnswers: unknown[] = Array.isArray(output) ? output : [];
    const input =
      "input" in part
        ? (part.input as { questions?: Record<string, JsonValue>[] } | undefined)
        : undefined;
    const rawQuestions = Array.isArray(input?.questions) ? input.questions : [];
    return {
      questions: rawQuestions.map(parseConsultQuestion),
      answers: rawAnswers
        .filter(
          (a): a is Record<string, JsonValue> => typeof a === "object" && a !== null,
        )
        .map(parseConsultAnswer),
    };
  }
  return null;
}

export function findPendingConsult(message: UIMessage): PendingConsult | null {
  for (const part of message.parts) {
    if (
      part.type === "tool-consult_user" &&
      "state" in part &&
      part.state === "approval-requested" &&
      "approval" in part
    ) {
      const input =
        "input" in part
          ? (part.input as { questions?: Record<string, JsonValue>[] } | undefined)
          : undefined;
      const rawQuestions = Array.isArray(input?.questions) ? input.questions : [];
      return {
        approvalId: part.approval.id,
        questions: rawQuestions.map(parseConsultQuestion),
        sourceMessage: message,
      };
    }
  }
  return null;
}

export function findPending(message: UIMessage): PendingApprovalInfo | null {
  for (const part of message.parts) {
    if (
      part.type === "tool-submit_plan_for_approval" &&
      "state" in part &&
      part.state === "approval-requested" &&
      "approval" in part
    ) {
      const input =
        "input" in part ? (part.input as { planId?: string } | undefined) : undefined;
      return {
        approvalId: part.approval.id,
        planId: input?.planId ?? null,
        sourceMessage: message,
      };
    }
  }
  return null;
}
