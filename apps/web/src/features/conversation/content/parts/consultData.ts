import type { JsonValue } from "@pathfinder/shared/generated/types/JsonValue";
import type { UIMessage } from "ai";

function strField(o: Record<string, JsonValue>, key: string): string {
  const v = o[key];
  return typeof v === "string" ? v : "";
}

function strList(o: Record<string, JsonValue>, key: string): string[] {
  const v = o[key];
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
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
