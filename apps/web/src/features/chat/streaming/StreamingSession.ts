import type { Strategy } from "@pathfinder/shared";

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
  undoSnapshot: Strategy | null = null;

  /** Whether at least one graph snapshot was applied during this session. */
  snapshotApplied = false;

  constructor() {}

  /**
   * Capture the current strategy as an undo point, but only once per
   * streaming session (the first mutation wins).
   */
  captureUndoSnapshot(graphId: string, currentStrategy: Strategy | null): void {
    if (!this.undoSnapshot && currentStrategy?.id === graphId) {
      this.undoSnapshot = currentStrategy;
    }
  }

  /** Mark that a snapshot was applied during this session. */
  markSnapshotApplied(): void {
    this.snapshotApplied = true;
  }

  /** Consume and clear the undo snapshot (returns ``null`` if already consumed). */
  consumeUndoSnapshot(): Strategy | null {
    const snapshot = this.undoSnapshot;
    this.undoSnapshot = null;
    return snapshot;
  }
}
