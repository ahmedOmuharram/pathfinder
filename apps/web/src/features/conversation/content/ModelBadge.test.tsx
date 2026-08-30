/**
 * @vitest-environment jsdom
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  AssistantRuntimeProvider,
  ThreadPrimitive,
  useExternalStoreRuntime,
  type MessageState,
  type ThreadMessageLike,
} from "@assistant-ui/react";

import { useSettingsStore } from "@/state/useSettingsStore";

import { ModelBadge, selectLeadUsage } from "./ModelBadge";

function assistant(content: unknown[]): MessageState {
  return { role: "assistant", content } as unknown as MessageState;
}

const USAGE_PART = {
  type: "data-lead-usage" as const,
  data: { modelId: "openai:gpt-5.6-luna", tokens: 41800, costUsd: "0.0131" },
};

function Harness({ content }: { content: ThreadMessageLike["content"] }) {
  const runtime = useExternalStoreRuntime<ThreadMessageLike>({
    messages: [{ role: "assistant", content }],
    convertMessage: (message) => message,
    onNew: async () => undefined,
  });
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ThreadPrimitive.Messages
        components={{ AssistantMessage: ModelBadge, UserMessage: () => null }}
      />
    </AssistantRuntimeProvider>
  );
}

describe("ModelBadge", () => {
  it("separates the model and the usage with an ASCII hyphen", () => {
    useSettingsStore.setState({ showTokenUsage: true });
    render(<Harness content={[USAGE_PART]} />);
    expect(screen.getByTestId("model-badge").textContent).toBe(
      "OpenAI-gpt-5.6-luna-41.8K, $0.01",
    );
  });

  it("draws no badge at all when the token flag is off", () => {
    useSettingsStore.setState({ showTokenUsage: false });
    render(<Harness content={[USAGE_PART]} />);
    expect(screen.queryAllByTestId("model-badge")).toHaveLength(0);
    useSettingsStore.setState({ showTokenUsage: true });
  });
});

describe("selectLeadUsage", () => {
  it("returns the latest lead-usage as a primitive string (no object - avoids React #185)", () => {
    const m = assistant([
      {
        type: "data-lead-usage",
        data: { modelId: "openai:gpt-4.1", tokens: 10, costUsd: "0.001" },
      },
      { type: "text", text: "hi" },
      {
        type: "data-lead-usage",
        data: { modelId: "openai:gpt-4.1", tokens: 120, costUsd: "0.004" },
      },
    ]);
    const result = selectLeadUsage(m);
    expect(typeof result).toBe("string");
    expect(result).toBe("openai:gpt-4.1\t120\t0.004");
  });

  it("matches the assistant-ui data shape (type=data, name)", () => {
    const m = assistant([
      {
        type: "data",
        name: "lead-usage",
        data: { modelId: "anthropic:claude", tokens: 5, costUsd: "0.01" },
      },
    ]);
    expect(selectLeadUsage(m)).toBe("anthropic:claude\t5\t0.01");
  });

  it("returns null when there is no lead-usage part", () => {
    expect(selectLeadUsage(assistant([{ type: "text", text: "hi" }]))).toBe(null);
  });

  it("returns null for non-assistant messages", () => {
    const user = { role: "user", content: [] } as unknown as MessageState;
    expect(selectLeadUsage(user)).toBe(null);
  });

  it("returns null when there is no message", () => {
    expect(selectLeadUsage(undefined)).toBe(null);
  });
});
