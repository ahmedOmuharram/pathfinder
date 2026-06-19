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
        type: "data-task-progress",
        data: { taskId: "t1", percent: 0.2, message: "1/5" },
      },
      {
        type: "data-task-progress",
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
        type: "data-task-progress",
        data: {
          taskId: "t1",
          percent: 0.3,
          message: "v1",
          toolSpecific: { variantId: "v1" },
        },
      },
      {
        type: "data-task-progress",
        data: {
          taskId: "t1",
          percent: 0.5,
          message: "v2",
          toolSpecific: { variantId: "v2" },
        },
      },
      {
        type: "data-task-progress",
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
        type: "data-task-progress",
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
        type: "data-task-progress",
        data: { taskId: "t1", percent: 0.6, message: "3/5" },
      },
      { type: "data-task-completed", data: { taskId: "t1", status: "success" } },
    ];
    const state = deriveTaskLiveState(chunks);
    expect(state.completed).toEqual({ taskId: "t1", status: "success" });
    expect(state.latest?.percent).toBe(0.6);
  });

  it("captures a failed completion with its error", () => {
    const chunks: TaskEventChunk[] = [
      {
        type: "data-task-completed",
        data: { taskId: "t1", status: "failed", error: "worker died" },
      },
    ];
    const state = deriveTaskLiveState(chunks);
    expect(state.completed?.status).toBe("failed");
    expect(state.completed?.error).toBe("worker died");
  });
});
