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
