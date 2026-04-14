// @vitest-environment jsdom
import { describe, expect, it, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import type { PathfinderUIMessage, Strategy } from "@pathfinder/shared";

import { useConversationTitleSync } from "./useConversationTitleSync";
import { strategiesListOptions } from "@/lib/api/strategies";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/strategy/store";
import { createTestQueryClient } from "@/lib/query/testing";

const SITE_ID = "plasmodb";
const CHAT_ID = "chat-123";

function assistantWithTitle(title: string): PathfinderUIMessage {
  return {
    id: "msg-1",
    role: "assistant",
    parts: [],
    metadata: { conversationTitle: title },
  };
}

function userMessage(): PathfinderUIMessage {
  return {
    id: "msg-user",
    role: "user",
    parts: [{ type: "text", text: "hi" }],
  };
}

function renderTitleSync(args: {
  chatId: string;
  messages: PathfinderUIMessage[];
  siteId?: string;
}) {
  const queryClient = createTestQueryClient();
  const Wrapper = ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);

  const { rerender } = renderHook(
    (props: { messages: PathfinderUIMessage[] }) =>
      useConversationTitleSync({
        chatId: args.chatId,
        messages: props.messages,
        siteId: args.siteId ?? SITE_ID,
      }),
    {
      wrapper: Wrapper,
      initialProps: { messages: args.messages },
    },
  );

  return {
    queryClient,
    rerender,
    listKey: strategiesListOptions(args.siteId ?? SITE_ID).queryKey,
  };
}

describe("useConversationTitleSync", () => {
  beforeEach(() => {
    useSessionStore.setState({ strategyId: null });
    useStrategyStore.setState({ strategy: null });
  });

  it("does nothing when chatId is empty", () => {
    const { queryClient, listKey } = renderTitleSync({
      chatId: "",
      messages: [assistantWithTitle("Should be ignored")],
    });

    expect(queryClient.getQueryData<Strategy[]>(listKey)).toBeUndefined();
  });

  it("does nothing when no assistant metadata carries a title", () => {
    const { queryClient, listKey } = renderTitleSync({
      chatId: CHAT_ID,
      messages: [userMessage(), { ...assistantWithTitle(""), metadata: {} }],
    });

    expect(queryClient.getQueryData<Strategy[]>(listKey)).toBeUndefined();
  });

  it("inserts a new sidebar row when the title arrives for an unknown chat", () => {
    const { queryClient, listKey } = renderTitleSync({
      chatId: CHAT_ID,
      messages: [userMessage(), assistantWithTitle("Plasmodium AP2 study")],
    });

    const list = queryClient.getQueryData<Strategy[]>(listKey);
    expect(list).toHaveLength(1);
    expect(list?.[0]).toMatchObject({
      id: CHAT_ID,
      name: "Plasmodium AP2 study",
      siteId: SITE_ID,
      isSaved: false,
      steps: [],
      rootStepId: null,
      recordType: null,
    });
  });

  it("updates existing sidebar row in place without duplicating it", () => {
    const queryClient = createTestQueryClient();
    const listKey = strategiesListOptions(SITE_ID).queryKey;
    const seed: Strategy = {
      id: CHAT_ID,
      name: "Old name",
      siteId: SITE_ID,
      recordType: null,
      steps: [],
      rootStepId: null,
      isSaved: false,
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-01T00:00:00Z",
    };
    queryClient.setQueryData<Strategy[]>(listKey, [seed]);

    const Wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client: queryClient }, children);

    renderHook(
      () =>
        useConversationTitleSync({
          chatId: CHAT_ID,
          messages: [userMessage(), assistantWithTitle("Updated name")],
          siteId: SITE_ID,
        }),
      { wrapper: Wrapper },
    );

    const list = queryClient.getQueryData<Strategy[]>(listKey);
    expect(list).toHaveLength(1);
    expect(list?.[0]?.name).toBe("Updated name");
    expect(list?.[0]?.createdAt).toBe("2026-01-01T00:00:00Z");
  });

  it("is idempotent when the same title arrives twice", () => {
    const { queryClient, rerender, listKey } = renderTitleSync({
      chatId: CHAT_ID,
      messages: [assistantWithTitle("Stable title")],
    });

    const firstList = queryClient.getQueryData<Strategy[]>(listKey);
    const firstUpdatedAt = firstList?.[0]?.updatedAt;

    rerender({ messages: [assistantWithTitle("Stable title")] });

    const secondList = queryClient.getQueryData<Strategy[]>(listKey);
    expect(secondList).toHaveLength(1);
    expect(secondList?.[0]?.updatedAt).toBe(firstUpdatedAt);
  });

  it("syncs strategy meta when chat matches active strategyId", () => {
    useSessionStore.setState({ strategyId: CHAT_ID });
    useStrategyStore.setState({
      strategy: {
        id: CHAT_ID,
        name: "Old strategy name",
        siteId: SITE_ID,
        recordType: null,
        steps: [],
        rootStepId: null,
        isSaved: false,
        createdAt: "2026-01-01T00:00:00Z",
        updatedAt: "2026-01-01T00:00:00Z",
      },
    });

    renderTitleSync({
      chatId: CHAT_ID,
      messages: [assistantWithTitle("Synced into store")],
    });

    expect(useStrategyStore.getState().strategy?.name).toBe("Synced into store");
  });

  it("does not touch strategy meta when active strategy differs", () => {
    useSessionStore.setState({ strategyId: "other-chat" });
    useStrategyStore.setState({
      strategy: {
        id: "other-chat",
        name: "Untouched",
        siteId: SITE_ID,
        recordType: null,
        steps: [],
        rootStepId: null,
        isSaved: false,
        createdAt: "2026-01-01T00:00:00Z",
        updatedAt: "2026-01-01T00:00:00Z",
      },
    });

    renderTitleSync({
      chatId: CHAT_ID,
      messages: [assistantWithTitle("Should not propagate")],
    });

    expect(useStrategyStore.getState().strategy?.name).toBe("Untouched");
  });
});
