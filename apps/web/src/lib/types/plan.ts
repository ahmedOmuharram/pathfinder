import { z } from "zod";

export type PlanStatus = "draft" | "presented" | "approved" | "executing" | "complete" | "failed";
export type StepStatus = "ready" | "needs_discovery" | "needs_user_input" | "executing" | "complete" | "failed";
export type StepType = "leaf" | "combine" | "transform";
export type ParamStatus = "set" | "default" | "needs_discovery" | "needs_user_input" | "user_set";

// ── Zod schemas (SSOT — interfaces are inferred from these) ────────

export const PlannedParameterSchema = z.object({
  name: z.string(),
  displayName: z.string(),
  paramType: z.string(),
  value: z.unknown().nullable(),
  status: z.enum(["set", "default", "needs_discovery", "needs_user_input", "user_set"]),
  required: z.boolean(),
  description: z.string().nullable(),
  constraints: z.record(z.string(), z.unknown()).nullable(),
  dependsOn: z.array(z.string()).default([]),
  vocabularySummary: z.string().nullable().default(null),
  question: z.string().nullable().default(null),
  options: z.array(z.string()).nullable().default(null),
  rationale: z.string().nullable().default(null),
});

export const QuestionOptionSchema = z.object({
  label: z.string(),
  description: z.string().default(""),
  pros: z.array(z.string()).default([]),
  cons: z.array(z.string()).default([]),
  recommended: z.boolean().default(false),
});

export const UserQuestionSchema = z.object({
  id: z.string(),
  question: z.string(),
  context: z.string().default(""),
  relatedStep: z.string().nullable().default(null),
  relatedParam: z.string().nullable().default(null),
  options: z.array(QuestionOptionSchema).nullable().default(null),
  answer: z.unknown().nullable().default(null),
});

export const PlannedStepSchema = z.object({
  id: z.string(),
  searchName: z.string(),
  displayName: z.string(),
  recordType: z.string().default("transcript"),
  rationale: z.string().default(""),
  stepType: z.enum(["leaf", "combine", "transform"]),
  status: z.enum(["ready", "needs_discovery", "needs_user_input", "executing", "complete", "failed"]),
  parameters: z.record(z.string(), PlannedParameterSchema).default({}),
  operator: z.string().nullable().default(null),
  expectedCount: z.number().nullable().default(null),
  actualCount: z.number().nullable().default(null),
  wdkStepId: z.number().nullable().default(null),
  graphStepId: z.string().nullable().default(null),
});

export const PlannedConnectionSchema = z.object({
  fromStep: z.string(),
  toStep: z.string(),
  inputType: z.string().default("primary"),
  operator: z.string().nullable().default(null),
});

export const InteractivePlanSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  rationale: z.string(),
  status: z.enum(["draft", "presented", "approved", "executing", "complete", "failed"]).default("draft"),
  version: z.number().default(1),
  steps: z.array(PlannedStepSchema).default([]),
  connections: z.array(PlannedConnectionSchema).default([]),
  questions: z.array(UserQuestionSchema).default([]),
  uncertainties: z.array(z.string()).default([]),
  createdAt: z.string().default(""),
  updatedAt: z.string().default(""),
});

// ── Inferred types (no manual interface duplication) ────────────────

export type PlannedParameter = z.infer<typeof PlannedParameterSchema>;
export type QuestionOption = z.infer<typeof QuestionOptionSchema>;
export type UserQuestion = z.infer<typeof UserQuestionSchema>;
export type PlannedStep = z.infer<typeof PlannedStepSchema>;
export type PlannedConnection = z.infer<typeof PlannedConnectionSchema>;
export type InteractivePlan = z.infer<typeof InteractivePlanSchema>;

export interface PlanParameterEdit {
  stepId: string;
  paramName: string;
  newValue: unknown;
}

export interface PlanQuestionAnswer {
  questionId: string;
  answer: unknown;
}

export interface PlanActionRequest {
  action: "approve" | "reject" | "suggest_changes";
  planId: string;
  traceId?: string | null;
  messageGroupId?: string | null;
  source?: string | null;
  paramEdits?: PlanParameterEdit[];
  answers?: PlanQuestionAnswer[];
}

export interface PlanInteractionMetadata {
  type: "plan_interaction";
  planId: string;
  action: "approve" | "update_parameter" | "answer_question" | "reject" | "suggest_changes";
  data: {
    stepId?: string;
    paramName?: string;
    newValue?: unknown;
    questionId?: string;
    answer?: unknown;
    suggestion?: string;
    paramEdits?: Array<{ stepId: string; paramName: string; newValue: unknown }>;
    answers?: Array<{ questionId: string; answer: unknown }>;
  };
}
