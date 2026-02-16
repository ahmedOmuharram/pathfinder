import type { StrategyWithMeta } from "@/types/strategy";

/**
 * Mutable state scoped to a single chat streaming session.
 *
 * A new instance is created at the start of every ``executeStream``
 * call and threaded through the SSE event handlers via
 * ``ChatEventContext``.  Because SSE events are processed
 * synchronously (no render cycle in-between), the fields are plain
 * mutable properties — no refs needed.
 */
export class StreamingSession {
  /** Undo snapshot captured before the first strategy mutation. */
  undoSnapshot: StrategyWithMeta | null = null;

  /** Whether at least one graph snapshot was applied during this session. */
  snapshotApplied = false;

  /** Latest strategy value, seeded at stream start and kept in sync via effect. */
  latestStrategy: StrategyWithMeta | null;

  constructor(initialStrategy: StrategyWithMeta | null) {
    this.latestStrategy = initialStrategy;
  }

  /**
   * Capture the current strategy as an undo point, but only once per
   * streaming session (the first mutation wins).
   */
  captureUndoSnapshot(graphId: string): void {
    const snapshot = this.latestStrategy;
    if (!this.undoSnapshot && snapshot && snapshot.id === graphId) {
      this.undoSnapshot = snapshot;
    }
  }

  /** Mark that a snapshot was applied during this session. */
  markSnapshotApplied(): void {
    this.snapshotApplied = true;
  }

  /** Consume and clear the undo snapshot (returns ``null`` if already consumed). */
  consumeUndoSnapshot(): StrategyWithMeta | null {
    const snapshot = this.undoSnapshot;
    this.undoSnapshot = null;
    return snapshot;
  }
}
