import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { conversationSnapshotOptions } from "./conversationSnapshot";

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
