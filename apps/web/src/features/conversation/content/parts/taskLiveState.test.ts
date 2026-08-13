import { describe, it, expect } from "vitest";

import { deriveTaskLiveState, type TaskEventChunk } from "./taskLiveState";

describe("deriveTaskLiveState", () => {
  it("returns empty state for no chunks", () => {
    const state = deriveTaskLiveState([]);
    expect(state).toEqual({ latest: null, completed: null, variants: new Map() });
  });

  it("tracks the most recent progress chunk as latest", () => {
    const chunks: TaskEventChunk[] = [
      {
        type: "custom",
        kind: "data-task-progress",
        data: { taskId: "t1", percent: 0.2, message: "1/5" },
      },
      {
        type: "custom",
        kind: "data-task-progress",
        data: { taskId: "t1", percent: 0.6, message: "3/5" },
      },
    ];
    const state = deriveTaskLiveState(chunks);
    expect(state.latest).toEqual({ taskId: "t1", percent: 0.6, message: "3/5" });
    expect(state.completed).toBeNull();
  });

  it("aggregates latest progress per fan-out variant", () => {
    const chunks: TaskEventChunk[] = [
      {
        type: "custom",
        kind: "data-task-progress",
        data: {
          taskId: "t1",
          percent: 0.3,
          message: "v1",
          toolSpecific: { variantId: "v1" },
        },
      },
      {
        type: "custom",
        kind: "data-task-progress",
        data: {
          taskId: "t1",
          percent: 0.5,
          message: "v2",
          toolSpecific: { variantId: "v2" },
        },
      },
      {
        type: "custom",
        kind: "data-task-progress",
        data: {
          taskId: "t1",
          percent: 0.9,
          message: "v1 done",
          toolSpecific: { variantId: "v1" },
        },
      },
    ];
    const state = deriveTaskLiveState(chunks);
    expect(state.variants.size).toBe(2);
    expect(state.variants.get("v1")?.percent).toBe(0.9);
    expect(state.variants.get("v1")?.message).toBe("v1 done");
    expect(state.variants.get("v2")?.percent).toBe(0.5);
  });

  it("ignores non-string variantId in toolSpecific", () => {
    const chunks: TaskEventChunk[] = [
      {
        type: "custom",
        kind: "data-task-progress",
        data: {
          taskId: "t1",
          percent: 0.4,
          message: "x",
          toolSpecific: { variantId: 7 },
        },
      },
    ];
    const state = deriveTaskLiveState(chunks);
    expect(state.variants.size).toBe(0);
    expect(state.latest?.percent).toBe(0.4);
  });

  it("captures terminal completion and its status", () => {
    const chunks: TaskEventChunk[] = [
      {
        type: "custom",
        kind: "data-task-progress",
        data: { taskId: "t1", percent: 0.6, message: "3/5" },
      },
      {
        type: "custom",
        kind: "data-task-completed",
        data: { taskId: "t1", status: "success" },
      },
    ];
    const state = deriveTaskLiveState(chunks);
    expect(state.completed).toEqual({ taskId: "t1", status: "success" });
    expect(state.latest?.percent).toBe(0.6);
  });

  it("captures a failed completion with its error", () => {
    const chunks: TaskEventChunk[] = [
      {
        type: "custom",
        kind: "data-task-completed",
        data: { taskId: "t1", status: "failed", error: "worker died" },
      },
    ];
    const state = deriveTaskLiveState(chunks);
    expect(state.completed?.status).toBe("failed");
    expect(state.completed?.error).toBe("worker died");
  });
});

describe("deriveTaskLiveState on the real wire shape", () => {
  // The endpoint frames every chunk as {type:"custom", kind:"data-task-*"}.
  // Reading `type` made every progress chunk look like a completion, and the
  // last one carried no status, so a task that succeeded rendered as failed.
  const progress = (percent: number, message: string): TaskEventChunk =>
    ({
      type: "custom",
      kind: "data-task-progress",
      data: { taskId: "t1", percent, message, toolSpecific: null },
    }) as unknown as TaskEventChunk;

  const completed = (status: string): TaskEventChunk =>
    ({
      type: "custom",
      kind: "data-task-completed",
      data: { taskId: "t1", status, error: null },
    }) as unknown as TaskEventChunk;

  const done = { type: "done", reason: "completed" } as unknown as TaskEventChunk;

  it("does not treat a progress chunk as a completion", () => {
    const state = deriveTaskLiveState([progress(0.5, "halfway")]);
    expect(state.completed).toBeNull();
    expect(state.latest?.percent).toBe(0.5);
  });

  it("reports a successful task as successful", () => {
    const state = deriveTaskLiveState([progress(1, "done"), completed("success")]);
    expect(state.completed?.status).toBe("success");
  });

  it("still reports a genuine failure", () => {
    const state = deriveTaskLiveState([progress(0.3, "working"), completed("failed")]);
    expect(state.completed?.status).toBe("failed");
  });

  it("ignores the stream terminator", () => {
    const state = deriveTaskLiveState([progress(1, "done"), done]);
    expect(state.completed).toBeNull();
  });
});
