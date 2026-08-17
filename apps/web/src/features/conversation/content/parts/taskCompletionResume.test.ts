import { describe, expect, it, vi } from "vitest";

import type { TaskEventChunk } from "./taskLiveState";
import { announceTaskCompletion } from "./taskCompletionResume";

const PROGRESS: TaskEventChunk = {
  type: "custom",
  kind: "data-task-progress",
  data: { message: "half way", percent: 50 } as never,
};

const COMPLETED: TaskEventChunk = {
  type: "custom",
  kind: "data-task-completed",
  data: { status: "complete" } as never,
};

async function* chunks(...items: TaskEventChunk[]): AsyncIterable<TaskEventChunk> {
  for (const item of items) yield item;
}

describe("announceTaskCompletion", () => {
  it("tells the caller once the task is complete", async () => {
    // The turn suspends on the task, so its answer only streams after the
    // task ends. Nothing else tells the open page to re-attach.
    const onComplete = vi.fn();

    for await (const _ of announceTaskCompletion(
      chunks(PROGRESS, COMPLETED),
      onComplete,
    ));

    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("announces when the stream ends without a terminal chunk", async () => {
    // A stream that opens while the task runs can end without the terminal
    // chunk. The turn's answer is already persisted either way.
    const onComplete = vi.fn();

    for await (const _ of announceTaskCompletion(chunks(PROGRESS), onComplete));

    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("announces once when both the chunk and the end arrive", async () => {
    const onComplete = vi.fn();

    for await (const _ of announceTaskCompletion(
      chunks(PROGRESS, COMPLETED),
      onComplete,
    ));

    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("announces even when the stream fails", async () => {
    const onComplete = vi.fn();
    async function* failing(): AsyncIterable<TaskEventChunk> {
      yield PROGRESS;
      throw new Error("connection lost");
    }

    await expect(async () => {
      for await (const _ of announceTaskCompletion(failing(), onComplete));
    }).rejects.toThrow("connection lost");
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("passes every chunk through unchanged", async () => {
    const seen: TaskEventChunk[] = [];

    for await (const chunk of announceTaskCompletion(
      chunks(PROGRESS, COMPLETED),
      () => {},
    )) {
      seen.push(chunk);
    }

    expect(seen).toEqual([PROGRESS, COMPLETED]);
  });

  it("announces completion before the stream ends", async () => {
    const order: string[] = [];

    for await (const chunk of announceTaskCompletion(chunks(PROGRESS, COMPLETED), () =>
      order.push("complete"),
    )) {
      order.push(
        chunk.type === "custom" && chunk.kind === "data-task-completed"
          ? "terminal"
          : "progress",
      );
    }

    expect(order).toEqual(["progress", "complete", "terminal"]);
  });
});
