import { describe, expect, it } from "vitest";
import type { Strategy } from "@pathfinder/shared";
import { StreamingSession } from "./StreamingSession";

function makeStrategy(overrides?: Partial<Strategy>): Strategy {
  return {
    id: overrides?.id ?? "strat-1",
    name: overrides?.name ?? "Test Strategy",
    siteId: overrides?.siteId ?? "plasmodb",
    recordType: overrides?.recordType ?? "gene",
    steps: overrides?.steps ?? [],
    rootStepId: overrides?.rootStepId ?? null,
    isSaved: overrides?.isSaved ?? false,
    createdAt: overrides?.createdAt ?? "2026-01-01T00:00:00Z",
    updatedAt: overrides?.updatedAt ?? "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("StreamingSession", () => {
  // ─── Constructor ───────────────────────────────────────────────────

  it("initializes with clean state", () => {
    const session = new StreamingSession();
    expect(session.undoSnapshot).toBeNull();
    expect(session.snapshotApplied).toBe(false);
  });

  // ─── captureUndoSnapshot ──────────────────────────────────────────

  it("captures the undo snapshot when graphId matches strategy id", () => {
    const strategy = makeStrategy({ id: "g1" });
    const session = new StreamingSession();
    session.captureUndoSnapshot("g1", strategy);
    expect(session.undoSnapshot).toBe(strategy);
  });

  it("does not capture when graphId does not match strategy id", () => {
    const strategy = makeStrategy({ id: "g1" });
    const session = new StreamingSession();
    session.captureUndoSnapshot("different-id", strategy);
    expect(session.undoSnapshot).toBeNull();
  });

  it("captures only on the first call (first mutation wins)", () => {
    const strategy1 = makeStrategy({ id: "g1", name: "First" });
    const session = new StreamingSession();
    session.captureUndoSnapshot("g1", strategy1);
    expect(session.undoSnapshot).toBe(strategy1);

    const strategy2 = makeStrategy({ id: "g1", name: "Second" });
    session.captureUndoSnapshot("g1", strategy2);
    // Should still be the first snapshot
    expect(session.undoSnapshot).toBe(strategy1);
    expect(session.undoSnapshot?.name).toBe("First");
  });

  it("does not capture when strategy is null", () => {
    const session = new StreamingSession();
    session.captureUndoSnapshot("g1", null);
    expect(session.undoSnapshot).toBeNull();
  });

  it("does not capture when undoSnapshot is already set (idempotent)", () => {
    const strategy = makeStrategy({ id: "g1" });
    const session = new StreamingSession();
    session.captureUndoSnapshot("g1", strategy);
    const firstSnapshot = session.undoSnapshot;

    session.captureUndoSnapshot("g1", strategy);
    expect(session.undoSnapshot).toBe(firstSnapshot);
  });

  // ─── markSnapshotApplied ──────────────────────────────────────────

  it("marks snapshot as applied", () => {
    const session = new StreamingSession();
    expect(session.snapshotApplied).toBe(false);
    session.markSnapshotApplied();
    expect(session.snapshotApplied).toBe(true);
  });

  it("remains true after multiple calls", () => {
    const session = new StreamingSession();
    session.markSnapshotApplied();
    session.markSnapshotApplied();
    expect(session.snapshotApplied).toBe(true);
  });

  // ─── consumeUndoSnapshot ──────────────────────────────────────────

  it("returns the snapshot and clears it", () => {
    const strategy = makeStrategy({ id: "g1" });
    const session = new StreamingSession();
    session.captureUndoSnapshot("g1", strategy);
    expect(session.undoSnapshot).toBe(strategy);

    const consumed = session.consumeUndoSnapshot();
    expect(consumed).toBe(strategy);
    expect(session.undoSnapshot).toBeNull();
  });

  it("returns null when no snapshot was captured", () => {
    const session = new StreamingSession();
    const consumed = session.consumeUndoSnapshot();
    expect(consumed).toBeNull();
  });

  it("returns null on second consume (already consumed)", () => {
    const strategy = makeStrategy({ id: "g1" });
    const session = new StreamingSession();
    session.captureUndoSnapshot("g1", strategy);

    const first = session.consumeUndoSnapshot();
    expect(first).toBe(strategy);

    const second = session.consumeUndoSnapshot();
    expect(second).toBeNull();
  });

  // ─── After consuming, capture is possible again ────────────────────

  it("allows recapture after consume clears the snapshot", () => {
    const strategy1 = makeStrategy({ id: "g1", name: "First" });
    const session = new StreamingSession();
    session.captureUndoSnapshot("g1", strategy1);
    session.consumeUndoSnapshot();

    const strategy2 = makeStrategy({ id: "g1", name: "Second" });
    session.captureUndoSnapshot("g1", strategy2);
    expect(session.undoSnapshot).toBe(strategy2);
  });

  // ─── Full lifecycle ────────────────────────────────────────────────

  it("supports a complete streaming session lifecycle", () => {
    const strategy = makeStrategy({ id: "g1" });
    const session = new StreamingSession();

    // 1. Capture undo before first mutation
    session.captureUndoSnapshot("g1", strategy);
    expect(session.undoSnapshot).toBe(strategy);

    // 2. Mark snapshot applied during mutation
    session.markSnapshotApplied();
    expect(session.snapshotApplied).toBe(true);

    // 3. Second capture attempt is ignored
    const updated = makeStrategy({ id: "g1", name: "After stream" });
    session.captureUndoSnapshot("g1", updated);
    expect(session.undoSnapshot).toBe(strategy); // still first

    // 4. Consume undo snapshot at end of session
    const undo = session.consumeUndoSnapshot();
    expect(undo).toBe(strategy);
    expect(session.undoSnapshot).toBeNull();

    // 5. State after consumption
    expect(session.snapshotApplied).toBe(true);
  });
});
