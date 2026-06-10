import { describe, expect, it } from "vitest";
import type { MessageState } from "@assistant-ui/react";

import { selectLeadUsage } from "./ModelBadge";

function assistant(content: unknown[]): MessageState {
  return { role: "assistant", content } as unknown as MessageState;
}

describe("selectLeadUsage", () => {
  it("returns the latest lead-usage as a primitive string (no object — avoids React #185)", () => {
    const m = assistant([
      { type: "data-lead-usage", data: { modelId: "openai:gpt-4.1", tokens: 10, costUsd: "0.001" } },
      { type: "text", text: "hi" },
      { type: "data-lead-usage", data: { modelId: "openai:gpt-4.1", tokens: 120, costUsd: "0.004" } },
    ]);
    const result = selectLeadUsage(m);
    expect(typeof result).toBe("string");
    expect(result).toBe("openai:gpt-4.1\t120\t0.004");
  });

  it("matches the assistant-ui data shape (type=data, name)", () => {
    const m = assistant([
      { type: "data", name: "lead-usage", data: { modelId: "anthropic:claude", tokens: 5, costUsd: "0.01" } },
    ]);
    expect(selectLeadUsage(m)).toBe("anthropic:claude\t5\t0.01");
  });

  it("returns null when there is no lead-usage part", () => {
    expect(selectLeadUsage(assistant([{ type: "text", text: "hi" }]))).toBeNull();
  });

  it("returns null for non-assistant messages", () => {
    const user = { role: "user", content: [] } as unknown as MessageState;
    expect(selectLeadUsage(user)).toBeNull();
  });

  it("returns null when there is no message", () => {
    expect(selectLeadUsage(undefined)).toBeNull();
  });
});
