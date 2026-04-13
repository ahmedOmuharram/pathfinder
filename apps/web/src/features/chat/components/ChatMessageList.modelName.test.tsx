/**
 * Regression tests for model name/icon display in <ChatMessageList />.
 *
 * These verify what actually renders in the `assistantName` label based
 * on `message.modelId` + `useModelCatalogQuery` catalog data.  The
 * retroactive stamping fix guarantees `modelId` lands on every assistant
 * message — these tests lock in the rendering half of that contract.
 *
 * @vitest-environment jsdom
 */

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type {
  AssistantMessage,
  Message,
  ModelCatalogEntry,
  ModelProvider,
} from "@pathfinder/shared";
import { ChatMessageList } from "@/features/chat/components/ChatMessageList";
import { useSessionStore } from "@/state/useSessionStore";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const useModelCatalogQueryMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/query/hooks/useModelCatalogQuery", () => ({
  useModelCatalogQuery: useModelCatalogQueryMock,
}));

// Capture ProviderIcon props so we can assert the provider in avatar.
const providerIconCalls = vi.hoisted(
  () => ({ calls: [] as { provider: ModelProvider; size: number }[] }),
);

vi.mock("@/lib/components/ProviderIcon", () => ({
  ProviderIcon: ({
    provider,
    size,
  }: {
    provider: ModelProvider;
    size: number;
  }) => {
    providerIconCalls.calls.push({ provider, size });
    return <span data-testid="provider-icon" data-provider={provider} />;
  },
}));

vi.mock("@/features/chat/components/ChatEmptyState", () => ({
  ChatEmptyState: () => null,
}));

vi.mock("@/features/chat/components/delegation/NodeCard", () => ({
  NodeCard: () => null,
}));

vi.mock("@/features/chat/components/message/ChatMarkdown", () => ({
  ChatMarkdown: ({ content }: { content: string }) => <span>{content}</span>,
}));

vi.mock("@/features/chat/components/thinking/ThinkingPanel", () => ({
  ThinkingPanel: () => null,
}));

vi.mock(
  "@/features/chat/components/optimization/OptimizationProgressPanel",
  () => ({
    OptimizationProgressPanel: () => null,
  }),
);

vi.mock("@/features/chat/components/message/AssistantMessageParts", () => ({
  AssistantMessageParts: ({ message }: { message: AssistantMessage }) => (
    <div data-testid="assistant-parts">{message.content}</div>
  ),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeCatalogEntry(
  overrides: Partial<ModelCatalogEntry> & { id: string; name: string },
): ModelCatalogEntry {
  return {
    id: overrides.id,
    name: overrides.name,
    provider: overrides.provider ?? "openai",
    model: overrides.model ?? overrides.id,
    description: overrides.description ?? "",
    supportsReasoning: overrides.supportsReasoning ?? false,
    contextSize: overrides.contextSize ?? 0,
    defaultReasoningBudget: overrides.defaultReasoningBudget ?? 0,
    inputPrice: overrides.inputPrice ?? 0,
    cachedInputPrice: overrides.cachedInputPrice ?? 0,
    outputPrice: overrides.outputPrice ?? 0,
    enabled: overrides.enabled ?? true,
  };
}

function makeAssistant(
  content: string,
  modelId: string | null | undefined,
): AssistantMessage {
  const base: AssistantMessage = {
    role: "assistant",
    content,
    timestamp: "2026-01-01T00:00:00.000Z",
  };
  if (modelId !== undefined) {
    base.modelId = modelId;
  }
  return base;
}

const baseProps = {
  isCompact: false,
  siteId: "PlasmoDB",
  displayName: "PlasmoDB",
  firstName: "Ahmed",
  fullName: "Ahmed Muharram",
  isStreaming: false,
  isLoading: false,
  undoSnapshots: {},
  onSend: vi.fn(),
  thinking: {
    activeMessageId: null,
    activeToolCalls: [],
    lastToolCalls: [],
    reasoning: null,
    getThinkingForMessage: () => ({
      activeToolCalls: [],
      lastToolCalls: [],
      reasoning: null,
    }),
  },
  messagesEndRef: { current: null } as React.RefObject<HTMLDivElement | null>,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  providerIconCalls.calls = [];
  useSessionStore.setState({ strategyId: "strategy-123" });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ChatMessageList — model name / avatar rendering", () => {
  it("renders the catalog `name` as the assistant label when modelId matches", () => {
    useModelCatalogQueryMock.mockReturnValue({
      data: {
        models: [
          makeCatalogEntry({
            id: "gpt-4",
            name: "GPT-4",
            provider: "openai",
          }),
        ],
        defaultProvider: "openai",
        defaultTier: "balanced",
      },
    });

    const messages: Message[] = [makeAssistant("hello", "gpt-4")];

    render(<ChatMessageList {...baseProps} messages={messages} />);

    // The label DIV immediately above AssistantMessageParts carries the name.
    // Assert the exact string, not just that *something* rendered.
    expect(screen.getByText("GPT-4")).toBeTruthy();
    // And the fallback text "Assistant" should NOT appear.
    expect(screen.queryByText("Assistant")).toBeNull();

    // The avatar's ProviderIcon should receive provider "openai".
    expect(
      providerIconCalls.calls.some((c) => c.provider === "openai"),
    ).toBe(true);
  });

  it("renders the fallback label 'Assistant' when modelId is null", () => {
    useModelCatalogQueryMock.mockReturnValue({
      data: {
        models: [
          makeCatalogEntry({
            id: "gpt-4",
            name: "GPT-4",
            provider: "openai",
          }),
        ],
        defaultProvider: "openai",
        defaultTier: "balanced",
      },
    });

    const messages: Message[] = [makeAssistant("hello", null)];

    render(<ChatMessageList {...baseProps} messages={messages} />);

    expect(screen.getByText("Assistant")).toBeTruthy();
    expect(screen.queryByText("GPT-4")).toBeNull();

    // Avatar falls back to the default "openai" provider.
    expect(
      providerIconCalls.calls.some((c) => c.provider === "openai"),
    ).toBe(true);
  });

  it("renders the fallback label 'Assistant' when modelId is not present in the catalog", () => {
    useModelCatalogQueryMock.mockReturnValue({
      data: {
        models: [
          makeCatalogEntry({
            id: "gpt-4",
            name: "GPT-4",
            provider: "openai",
          }),
        ],
        defaultProvider: "openai",
        defaultTier: "balanced",
      },
    });

    const messages: Message[] = [
      makeAssistant("hello", "some-unknown-model-id"),
    ];

    render(<ChatMessageList {...baseProps} messages={messages} />);

    // Catalog lookup misses — component falls back to "Assistant".
    expect(screen.getByText("Assistant")).toBeTruthy();
    expect(screen.queryByText("GPT-4")).toBeNull();

    // Avatar also falls back to the default provider icon "openai".
    expect(
      providerIconCalls.calls.some((c) => c.provider === "openai"),
    ).toBe(true);
  });

  it("renders anthropic-provided model with provider icon 'anthropic'", () => {
    useModelCatalogQueryMock.mockReturnValue({
      data: {
        models: [
          makeCatalogEntry({
            id: "claude-opus-4",
            name: "Claude Opus 4",
            provider: "anthropic",
          }),
        ],
        defaultProvider: "anthropic",
        defaultTier: "quality",
      },
    });

    const messages: Message[] = [makeAssistant("hi", "claude-opus-4")];

    render(<ChatMessageList {...baseProps} messages={messages} />);

    expect(screen.getByText("Claude Opus 4")).toBeTruthy();
    expect(
      providerIconCalls.calls.some((c) => c.provider === "anthropic"),
    ).toBe(true);
  });
});
