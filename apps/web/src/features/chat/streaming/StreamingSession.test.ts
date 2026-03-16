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

  it("initializes with the provided strategy", () => {
    const strategy = makeStrategy();
    const session = new StreamingSession(strategy);
    expect(session.latestStrategy).toBe(strategy);
    expect(session.undoSnapshot).toBeNull();
    expect(session.snapshotApplied).toBe(false);
  });

  it("initializes with null strategy", () => {
    const session = new StreamingSession(null);
    expect(session.latestStrategy).toBeNull();
    expect(session.undoSnapshot).toBeNull();
    expect(session.snapshotApplied).toBe(false);
  });

  // ─── captureUndoSnapshot ──────────────────────────────────────────

  it("captures the undo snapshot when graphId matches strategy id", () => {
    const strategy = makeStrategy({ id: "g1" });
    const session = new StreamingSession(strategy);
    session.captureUndoSnapshot("g1");
    expect(session.undoSnapshot).toBe(strategy);
  });

  it("does not capture when graphId does not match strategy id", () => {
    const strategy = makeStrategy({ id: "g1" });
    const session = new StreamingSession(strategy);
    session.captureUndoSnapshot("different-id");
    expect(session.undoSnapshot).toBeNull();
  });

  it("captures only on the first call (first mutation wins)", () => {
    const strategy1 = makeStrategy({ id: "g1", name: "First" });
    const session = new StreamingSession(strategy1);
    session.captureUndoSnapshot("g1");
    expect(session.undoSnapshot).toBe(strategy1);

    // Update latestStrategy and try to capture again
    const strategy2 = makeStrategy({ id: "g1", name: "Second" });
    session.latestStrategy = strategy2;
    session.captureUndoSnapshot("g1");
    // Should still be the first snapshot
    expect(session.undoSnapshot).toBe(strategy1);
    expect(session.undoSnapshot?.name).toBe("First");
  });

  it("does not capture when latestStrategy is null", () => {
    const session = new StreamingSession(null);
    session.captureUndoSnapshot("g1");
    expect(session.undoSnapshot).toBeNull();
  });

  it("does not capture when undoSnapshot is already set (idempotent)", () => {
    const strategy = makeStrategy({ id: "g1" });
    const session = new StreamingSession(strategy);
    session.captureUndoSnapshot("g1");
    const firstSnapshot = session.undoSnapshot;

    // Even with a new strategy that matches, snapshot should not change
    session.latestStrategy = makeStrategy({ id: "g1", name: "Updated" });
    session.captureUndoSnapshot("g1");
    expect(session.undoSnapshot).toBe(firstSnapshot);
  });

  // ─── markSnapshotApplied ──────────────────────────────────────────

  it("marks snapshot as applied", () => {
    const session = new StreamingSession(null);
    expect(session.snapshotApplied).toBe(false);
    session.markSnapshotApplied();
    expect(session.snapshotApplied).toBe(true);
  });

  it("remains true after multiple calls", () => {
    const session = new StreamingSession(null);
    session.markSnapshotApplied();
    session.markSnapshotApplied();
    expect(session.snapshotApplied).toBe(true);
  });

  // ─── consumeUndoSnapshot ──────────────────────────────────────────

  it("returns the snapshot and clears it", () => {
    const strategy = makeStrategy({ id: "g1" });
    const session = new StreamingSession(strategy);
    session.captureUndoSnapshot("g1");
    expect(session.undoSnapshot).toBe(strategy);

    const consumed = session.consumeUndoSnapshot();
    expect(consumed).toBe(strategy);
    expect(session.undoSnapshot).toBeNull();
  });

  it("returns null when no snapshot was captured", () => {
    const session = new StreamingSession(makeStrategy());
    const consumed = session.consumeUndoSnapshot();
    expect(consumed).toBeNull();
  });

  it("returns null on second consume (already consumed)", () => {
    const strategy = makeStrategy({ id: "g1" });
    const session = new StreamingSession(strategy);
    session.captureUndoSnapshot("g1");

    const first = session.consumeUndoSnapshot();
    expect(first).toBe(strategy);

    const second = session.consumeUndoSnapshot();
    expect(second).toBeNull();
  });

  // ─── After consuming, capture is possible again ────────────────────

  it("allows recapture after consume clears the snapshot", () => {
    const strategy1 = makeStrategy({ id: "g1", name: "First" });
    const session = new StreamingSession(strategy1);
    session.captureUndoSnapshot("g1");
    session.consumeUndoSnapshot();

    const strategy2 = makeStrategy({ id: "g1", name: "Second" });
    session.latestStrategy = strategy2;
    session.captureUndoSnapshot("g1");
    expect(session.undoSnapshot).toBe(strategy2);
  });

  // ─── latestStrategy is mutable ─────────────────────────────────────

  it("allows direct mutation of latestStrategy", () => {
    const session = new StreamingSession(null);
    const strategy = makeStrategy({ id: "new" });
    session.latestStrategy = strategy;
    expect(session.latestStrategy).toBe(strategy);
  });

  it("captureUndoSnapshot uses the current latestStrategy value", () => {
    const initial = makeStrategy({ id: "g1", name: "Initial" });
    const session = new StreamingSession(initial);

    // Update latestStrategy before capturing
    const updated = makeStrategy({ id: "g1", name: "Updated" });
    session.latestStrategy = updated;
    session.captureUndoSnapshot("g1");

    expect(session.undoSnapshot).toBe(updated);
  });

  // ─── Full lifecycle ────────────────────────────────────────────────

  it("supports a complete streaming session lifecycle", () => {
    const strategy = makeStrategy({ id: "g1" });
    const session = new StreamingSession(strategy);

    // 1. Capture undo before first mutation
    session.captureUndoSnapshot("g1");
    expect(session.undoSnapshot).toBe(strategy);

    // 2. Mark snapshot applied during mutation
    session.markSnapshotApplied();
    expect(session.snapshotApplied).toBe(true);

    // 3. Update latestStrategy as stream progresses
    const updated = makeStrategy({ id: "g1", name: "After stream" });
    session.latestStrategy = updated;

    // 4. Second capture attempt is ignored
    session.captureUndoSnapshot("g1");
    expect(session.undoSnapshot).toBe(strategy); // still first

    // 5. Consume undo snapshot at end of session
    const undo = session.consumeUndoSnapshot();
    expect(undo).toBe(strategy);
    expect(session.undoSnapshot).toBeNull();

    // 6. State after consumption
    expect(session.latestStrategy).toBe(updated);
    expect(session.snapshotApplied).toBe(true);
  });
});
