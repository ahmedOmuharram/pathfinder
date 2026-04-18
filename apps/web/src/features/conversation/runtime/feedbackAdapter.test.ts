/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

import { createFeedbackAdapter } from "./feedbackAdapter";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const { requestVoid } = vi.hoisted(() => ({
  requestVoid: vi.fn(),
}));
vi.mock("@/lib/api/http", () => ({ requestVoid }));

type AssistantMsg = {
  id: string;
  role: "assistant";
  content: Array<
    | { type: "text"; text: string }
    | { type: "data"; name: string; data: Record<string, unknown> }
  >;
};

function mkMessage(id: string, traceId: string | null): AssistantMsg {
  const content: AssistantMsg["content"] = [];
  if (traceId !== null) {
    content.push({
      type: "data",
      name: "phase-start",
      data: { traceId, phase: "scoping", model: "gpt" },
    });
  }
  content.push({ type: "text", text: "ok" });
  return { id, role: "assistant", content };
}

describe("feedbackAdapter", () => {
  beforeEach(() => {
    requestVoid.mockReset();
    requestVoid.mockResolvedValue(undefined);
  });

  it("posts positive feedback with traceId extracted from phase-start", async () => {
    const adapter = createFeedbackAdapter();
    adapter.submit({
      message: mkMessage("msg-1", "trace-abc") as never,
      type: "positive",
    });
    await Promise.resolve();
    await Promise.resolve();
    expect(requestVoid).toHaveBeenCalledWith("/api/v1/feedback", {
      method: "POST",
      body: { traceId: "trace-abc", streamId: "msg-1", value: 1 },
    });
  });

  it("posts negative feedback with value=0", async () => {
    const adapter = createFeedbackAdapter();
    adapter.submit({
      message: mkMessage("msg-2", "trace-xyz") as never,
      type: "negative",
    });
    await Promise.resolve();
    await Promise.resolve();
    expect(requestVoid).toHaveBeenCalledWith("/api/v1/feedback", {
      method: "POST",
      body: { traceId: "trace-xyz", streamId: "msg-2", value: 0 },
    });
  });

  it("toasts an error and skips the POST when no traceId is present", async () => {
    const { toast } = await import("sonner");
    const adapter = createFeedbackAdapter();
    adapter.submit({
      message: mkMessage("msg-3", null) as never,
      type: "positive",
    });
    await Promise.resolve();
    expect(requestVoid).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalled();
  });
});
