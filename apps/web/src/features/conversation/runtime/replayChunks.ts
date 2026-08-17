/**
 * The conversation event log holds the user's own messages so a snapshot can
 * rebuild the transcript. They are not AI SDK chunks, so a replayed stream
 * has to drop them before the chunk schema sees them.
 */
const SNAPSHOT_ONLY_TYPE = "user-message";

export function isTransportChunk(data: string): boolean {
  let parsed: unknown;
  try {
    parsed = JSON.parse(data);
  } catch {
    return true;
  }
  return (
    typeof parsed !== "object" ||
    parsed === null ||
    (parsed as { type?: unknown }).type !== SNAPSHOT_ONLY_TYPE
  );
}
