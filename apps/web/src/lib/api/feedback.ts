import { requestVoid } from "./http";

export async function submitFeedback(params: {
  traceId: string;
  streamId: string;
  value: number;
  comment?: string;
}): Promise<void> {
  await requestVoid("/api/v1/feedback", {
    method: "POST",
    body: params,
  });
}

export async function submitProductAction(params: {
  action:
    | "plan_approve"
    | "plan_reject"
    | "plan_suggest_changes"
    | "plan_ask_question"
    | "undo_turn"
    | "assistant_regenerate";
  streamId: string;
  traceId?: string | null;
  strategyId?: string | null;
  planId?: string | null;
  entryId?: string | null;
  messageGroupId?: string | null;
  metadata?: Record<string, unknown>;
}): Promise<void> {
  await requestVoid("/api/v1/feedback/actions", {
    method: "POST",
    body: params,
  });
}
