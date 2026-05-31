import { describe, it, expect, beforeEach } from "vitest";
import { useTaskStore } from "./useTaskStore";

describe("state/useTaskStore", () => {
  beforeEach(() => {
    useTaskStore.getState().reset();
  });

  it("starts empty", () => {
    expect(useTaskStore.getState().tasks).toEqual({});
  });

  it("startTask records a task keyed by id", () => {
    useTaskStore.getState().startTask({
      taskId: "t1",
      toolName: "run_control_tests_on_step",
      startedAt: "2026-04-14T00:00:00Z",
      estimatedDurationSeconds: 60,
    });
    expect(Object.keys(useTaskStore.getState().tasks)).toEqual(["t1"]);
    const record = useTaskStore.getState().tasks["t1"];
    expect(record).toBeDefined();
    if (!record) throw new Error("expected record for t1");
    expect(record.status).toBe("running");
    expect(record.toolName).toBe("run_control_tests_on_step");
    expect(record.lastProgress).toBeNull();
  });

  it("setProgress stores the latest progress frame", () => {
    useTaskStore.getState().startTask({
      taskId: "t1",
      toolName: "x",
      startedAt: new Date().toISOString(),
      estimatedDurationSeconds: 30,
    });
    useTaskStore.getState().setProgress("t1", {
      percent: 0.5,
      message: "halfway",
      toolSpecific: { step: 2, total: 4 },
    });
    const record = useTaskStore.getState().tasks["t1"];
    if (!record) throw new Error("expected record");
    expect(record.lastProgress?.percent).toBe(0.5);
    expect(record.lastProgress?.message).toBe("halfway");
    expect(record.lastProgress?.toolSpecific).toEqual({ step: 2, total: 4 });
  });

  it("setProgress for unknown task is a no-op", () => {
    useTaskStore.getState().setProgress("nope", { percent: 0.1, message: "ignored" });
    expect(useTaskStore.getState().tasks).toEqual({});
  });

  it("completeTask flips status to success and keeps last progress", () => {
    useTaskStore.getState().startTask({
      taskId: "t1",
      toolName: "x",
      startedAt: new Date().toISOString(),
      estimatedDurationSeconds: 60,
    });
    useTaskStore.getState().setProgress("t1", { percent: 1, message: "done" });
    useTaskStore.getState().completeTask("t1", "success");
    const record = useTaskStore.getState().tasks["t1"];
    if (!record) throw new Error("expected record");
    expect(record.status).toBe("success");
    expect(record.lastProgress?.percent).toBe(1);
    expect(record.error).toBeUndefined();
  });

  it("completeTask records failure message", () => {
    useTaskStore.getState().startTask({
      taskId: "t1",
      toolName: "x",
      startedAt: new Date().toISOString(),
      estimatedDurationSeconds: 60,
    });
    useTaskStore.getState().completeTask("t1", "failed", "boom");
    const record = useTaskStore.getState().tasks["t1"];
    if (!record) throw new Error("expected record");
    expect(record.status).toBe("failed");
    expect(record.error).toBe("boom");
  });

  it("completeTask for unknown task is a no-op", () => {
    useTaskStore.getState().completeTask("nope", "success");
    expect(useTaskStore.getState().tasks).toEqual({});
  });

  it("startTask is idempotent by taskId — calling twice replaces the record", () => {
    useTaskStore.getState().startTask({
      taskId: "t1",
      toolName: "first",
      startedAt: "2026-04-14T00:00:00Z",
      estimatedDurationSeconds: 30,
    });
    useTaskStore.getState().startTask({
      taskId: "t1",
      toolName: "second",
      startedAt: "2026-04-14T00:01:00Z",
      estimatedDurationSeconds: 60,
    });
    const record = useTaskStore.getState().tasks["t1"];
    if (!record) throw new Error("expected record");
    expect(record.toolName).toBe("second");
    expect(record.estimatedDurationSeconds).toBe(60);
  });

  it("reset clears all tasks", () => {
    useTaskStore.getState().startTask({
      taskId: "t1",
      toolName: "x",
      startedAt: new Date().toISOString(),
      estimatedDurationSeconds: 60,
    });
    useTaskStore.getState().reset();
    expect(useTaskStore.getState().tasks).toEqual({});
  });
});
