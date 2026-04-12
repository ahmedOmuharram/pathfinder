import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Strategy, UserMessage, Message } from "@pathfinder/shared";
import { undoTurnAction } from "./undoTurnAction";
import type { UndoTurnDeps } from "./undoTurnAction";

vi.mock("@/lib/api/strategies", () => ({
  undoTurn: vi.fn(),
  getStrategy: vi.fn(),
}));

import { undoTurn, getStrategy } from "@/lib/api/strategies";

const mockUndoTurn = vi.mocked(undoTurn);
const mockGetStrategy = vi.mocked(getStrategy);

function makeUserMessage(content: string, entryId?: string, traceId?: string): UserMessage {
  return {
    role: "user",
    content,
    timestamp: "2026-01-01T00:00:00Z",
    ...(entryId != null ? { entryId } : {}),
    ...(traceId != null ? { traceId } : {}),
  };
}

function makeStrategy(overrides?: Partial<Strategy>): Strategy {
  return {
    id: "strat-1",
    name: "Test",
    siteId: "plasmodb",
    recordType: "transcript",
    steps: [],
    rootStepId: null,
    isSaved: false,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeDeps(): UndoTurnDeps & { calls: Record<string, unknown[]> } {
  const calls: Record<string, unknown[]> = {};
  return {
    calls,
    setMessages: vi.fn((updater) => {
      if (typeof updater === "function") {
        calls["setMessages"] = [updater];
      }
    }),
    setUndoSnapshots: vi.fn((updater) => {
      if (typeof updater === "function") {
        calls["setUndoSnapshots"] = [updater];
      }
    }),
    setStrategy: vi.fn(),
    setStrategyMeta: vi.fn(),
    setComposerPrefill: vi.fn(),
  };
}

describe("undoTurnAction", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns false when entryId is missing", async () => {
    const deps = makeDeps();
    const msg = makeUserMessage("hello");
    const result = await undoTurnAction("strat-1", msg, 0, deps);
    expect(result).toBe(false);
    expect(mockUndoTurn).not.toHaveBeenCalled();
  });

  it("returns false when entryId is empty", async () => {
    const deps = makeDeps();
    const msg = makeUserMessage("hello", "");
    const result = await undoTurnAction("strat-1", msg, 0, deps);
    expect(result).toBe(false);
    expect(mockUndoTurn).not.toHaveBeenCalled();
  });

  it("calls undoTurn, truncates messages, and restores strategy when present", async () => {
    const fullStrategy = makeStrategy({ name: "Restored" });
    mockUndoTurn.mockResolvedValue({
      messageCount: 2,
      strategy: { id: "strat-1" },
      wdkStrategyId: 42,
    });
    mockGetStrategy.mockResolvedValue(fullStrategy);

    const deps = makeDeps();
    const msg = makeUserMessage("undo me", "entry-123", "trace-123");
    const result = await undoTurnAction("strat-1", msg, 2, deps);

    expect(result).toBe(true);
    expect(mockUndoTurn).toHaveBeenCalledWith("strat-1", "entry-123", "trace-123");

    // setMessages called with truncation updater
    expect(deps.setMessages).toHaveBeenCalled();
    const messagesUpdater = (deps.setMessages as ReturnType<typeof vi.fn>).mock.calls[0]![0] as (prev: Message[]) => Message[];
    const fakeMessages: Message[] = [
      makeUserMessage("m1"),
      { role: "assistant", content: "r1", timestamp: "t" },
      makeUserMessage("undo me", "entry-123"),
      { role: "assistant", content: "r2", timestamp: "t" },
    ];
    expect(messagesUpdater(fakeMessages)).toEqual([fakeMessages[0], fakeMessages[1]]);

    // Strategy restored
    expect(mockGetStrategy).toHaveBeenCalledWith("strat-1");
    expect(deps.setStrategy).toHaveBeenCalledWith(fullStrategy);
    expect(deps.setStrategyMeta).toHaveBeenCalledWith({
      name: "Restored",
      recordType: "transcript",
    });

    // Composer prefilled
    expect(deps.setComposerPrefill).toHaveBeenCalledWith({ message: "undo me" });
  });

  it("clears strategy when undo result has no strategy", async () => {
    mockUndoTurn.mockResolvedValue({
      messageCount: 0,
      strategy: null,
      wdkStrategyId: null,
    });

    const deps = makeDeps();
    const msg = makeUserMessage("clear me", "entry-456");
    const result = await undoTurnAction("strat-1", msg, 0, deps);

    expect(result).toBe(true);
    expect(deps.setStrategy).toHaveBeenCalledWith(null);
    expect(deps.setStrategyMeta).toHaveBeenCalledWith({});
    expect(mockGetStrategy).not.toHaveBeenCalled();
  });

  it("truncates undo snapshots to before the undo index", async () => {
    mockUndoTurn.mockResolvedValue({
      messageCount: 1,
      strategy: null,
      wdkStrategyId: null,
    });

    const deps = makeDeps();
    const msg = makeUserMessage("undo", "entry-789");
    await undoTurnAction("strat-1", msg, 3, deps);

    const snapshotsUpdater = (deps.setUndoSnapshots as ReturnType<typeof vi.fn>).mock.calls[0]![0] as (prev: Record<number, Strategy>) => Record<number, Strategy>;
    const fakeSnapshots: Record<number, Strategy> = {
      1: makeStrategy({ name: "s1" }),
      3: makeStrategy({ name: "s3" }),
      5: makeStrategy({ name: "s5" }),
    };
    const result = snapshotsUpdater(fakeSnapshots);
    expect(result).toEqual({ 1: fakeSnapshots[1] });
  });
});
