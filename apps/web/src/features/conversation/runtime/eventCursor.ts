const CURSOR_PREFIX = "pathfinder:event-cursor:";

export function readCursor(conversationId: string): number {
  if (typeof window === "undefined") return 0;
  const raw = window.localStorage.getItem(CURSOR_PREFIX + conversationId);
  if (raw === null) return 0;
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
}

export function writeCursor(conversationId: string, id: number): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(CURSOR_PREFIX + conversationId, String(id));
}
