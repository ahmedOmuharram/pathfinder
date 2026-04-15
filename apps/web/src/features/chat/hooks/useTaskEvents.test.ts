import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

import { useTaskStore } from "@/state/useTaskStore";

import { createTaskEventSubscription } from "./useTaskEvents";

type MessageHandler = (ev: MessageEvent<string>) => void;
type ErrorHandler = () => void;

class MockEventSource {
  static instances: MockEventSource[] = [];
  public onmessage: MessageHandler | null = null;
  public onerror: ErrorHandler | null = null;
  public closed = false;
  constructor(
    public readonly url: string,
    public readonly init: { withCredentials?: boolean } | undefined,
  ) {
    MockEventSource.instances.push(this);
  }
  emit(payload: unknown): void {
    this.onmessage?.({
      data: JSON.stringify(payload),
    } as MessageEvent<string>);
  }
  fail(): void {
    this.onerror?.();
  }
  close(): void {
    this.closed = true;
  }
}

function makeSubscription() {
  const changes = { count: 0 };
  const onChange = (): void => {
    changes.count += 1;
  };
  const cleanup = createTaskEventSubscription(
    {
      chatId: "chat-1",
      taskId: "task-1",
      EventSourceImpl: MockEventSource as unknown as new (
        url: string,
        init?: { withCredentials?: boolean },
      ) => EventSource,
      setProgress: (id, p) => {
        useTaskStore.getState().setProgress(id, p);
      },
      completeTask: (id, status, error) => {
        useTaskStore.getState().completeTask(id, status, error);
      },
    },
    onChange,
  );
  return { changes, cleanup };
}

beforeEach(() => {
  MockEventSource.instances = [];
  useTaskStore.getState().reset();
  useTaskStore.getState().startTask({
    taskId: "task-1",
    toolName: "x",
    startedAt: new Date().toISOString(),
    estimatedDurationSeconds: 60,
  });
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useTaskEvents (createTaskEventSubscription)", () => {
  it("opens an SSE connection with credentials and the correct URL", () => {
    const { cleanup } = makeSubscription();
    expect(MockEventSource.instances).toHaveLength(1);
    const source = MockEventSource.instances[0];
    if (!source) throw new Error("expected source");
    expect(source.url).toBe("/api/v1/chats/chat-1/tasks/task-1/events");
    expect(source.init?.withCredentials).toBe(true);
    cleanup();
  });

  it("dispatches data-task-progress chunks to the store", () => {
    const { cleanup, changes } = makeSubscription();
    const source = MockEventSource.instances[0];
    if (!source) throw new Error("expected source");
    source.emit({
      type: "data-task-progress",
      data: {
        taskId: "task-1",
        percent: 0.25,
        message: "step 1",
        toolSpecific: { foo: 1 },
      },
    });
    const record = useTaskStore.getState().tasks["task-1"];
    if (!record) throw new Error("expected record");
    expect(record.lastProgress?.percent).toBe(0.25);
    expect(record.lastProgress?.message).toBe("step 1");
    expect(record.lastProgress?.toolSpecific).toEqual({ foo: 1 });
    expect(changes.count).toBeGreaterThan(0);
    cleanup();
  });

  it("marks task success on data-task-completed and closes the source", () => {
    const { cleanup } = makeSubscription();
    const source = MockEventSource.instances[0];
    if (!source) throw new Error("expected source");
    source.emit({
      type: "data-task-completed",
      data: { taskId: "task-1", status: "success" },
    });
    const record = useTaskStore.getState().tasks["task-1"];
    if (!record) throw new Error("expected record");
    expect(record.status).toBe("success");
    expect(source.closed).toBe(true);
    cleanup();
  });

  it("marks failure with error string", () => {
    const { cleanup } = makeSubscription();
    const source = MockEventSource.instances[0];
    if (!source) throw new Error("expected source");
    source.emit({
      type: "data-task-completed",
      data: { taskId: "task-1", status: "failed", error: "boom" },
    });
    const record = useTaskStore.getState().tasks["task-1"];
    if (!record) throw new Error("expected record");
    expect(record.status).toBe("failed");
    expect(record.error).toBe("boom");
    cleanup();
  });

  it("ignores malformed SSE payloads", () => {
    const { cleanup } = makeSubscription();
    const source = MockEventSource.instances[0];
    if (!source) throw new Error("expected source");
    source.onmessage?.({ data: "not-json" } as MessageEvent<string>);
    source.onmessage?.({
      data: JSON.stringify({ type: "data-task-progress" }),
    } as MessageEvent<string>);
    const record = useTaskStore.getState().tasks["task-1"];
    if (!record) throw new Error("expected record");
    expect(record.lastProgress).toBeNull();
    cleanup();
  });

  it("reconnects with exponential backoff (1s, 2s, 4s, 8s, 16s) for up to 5 attempts, then stops", () => {
    const { cleanup } = makeSubscription();
    expect(MockEventSource.instances).toHaveLength(1);
    const delays = [1000, 2000, 4000, 8000, 16000];
    for (const [index, delay] of delays.entries()) {
      const current = MockEventSource.instances[index];
      if (!current) throw new Error(`expected instance ${index}`);
      current.fail();
      vi.advanceTimersByTime(delay);
      expect(MockEventSource.instances).toHaveLength(index + 2);
    }
    // 6th connection is open. Fail again → attempt counter has hit the cap,
    // so no further reconnect is scheduled.
    const last = MockEventSource.instances[5];
    if (!last) throw new Error("expected 6th instance");
    last.fail();
    vi.advanceTimersByTime(60000);
    expect(MockEventSource.instances).toHaveLength(6);
    cleanup();
  });

  it("cleanup closes the open source and cancels pending reconnects", () => {
    const { cleanup } = makeSubscription();
    const source = MockEventSource.instances[0];
    if (!source) throw new Error("expected source");
    source.fail();
    cleanup();
    vi.advanceTimersByTime(5000);
    expect(MockEventSource.instances).toHaveLength(1);
    expect(source.closed).toBe(true);
  });
});
