import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { conversationSnapshotOptions, reduceSnapshotChunks } from "./conversationSnapshot";

describe("reduceSnapshotChunks", () => {
  it("keeps a queued status part on the assistant message it precedes", async () => {
    const chunks = [
      { type: "data-turn-status", data: { label: "Queued" } },
      { type: "start", messageId: "assistant-1" },
      { type: "text-start", id: "t1" },
      { type: "text-delta", id: "t1", delta: "hello" },
      { type: "text-end", id: "t1" },
      { type: "finish", finishReason: "stop" },
      { type: "done" },
    ];

    const messages = await reduceSnapshotChunks(chunks);

    expect(messages).toHaveLength(1);
    expect(messages).toMatchObject([
      {
        id: "assistant-1",
        role: "assistant",
        parts: [
          { type: "data-turn-status", data: { label: "Queued" } },
          { type: "text", text: "hello" },
        ],
      },
    ]);
  });
});

describe("conversationSnapshotOptions", () => {
  it("re-reads the transcript for every mount", async () => {
    // A turn appends messages the cached snapshot does not have, so a cached
    // snapshot served to a later mount shows a shorter transcript than exists.
    const client = new QueryClient();
    const options = conversationSnapshotOptions("c1");
    const queryFn = vi.fn().mockResolvedValue([]);
    const observer = new QueryObserver(client, { ...options, queryFn });

    const unsubscribe = observer.subscribe(() => {});
    await observer.refetch();
    unsubscribe();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(client.getQueryData(options.queryKey)).toBeUndefined();
  });

  it("does not refetch while a single mount is open", () => {
    expect(conversationSnapshotOptions("c1").staleTime).toBe(Infinity);
  });
});
