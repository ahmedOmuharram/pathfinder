export const TYPED_EVENT_DONE = "[DONE]";

const FRAME_TERMINATOR = "\n\n";
const DATA_FIELD = "data: ";

function lastDataLine(frame: string): string | null {
  let dataLine: string | null = null;
  for (const line of frame.split("\n")) {
    if (line.startsWith(DATA_FIELD)) dataLine = line.slice(DATA_FIELD.length);
  }
  return dataLine;
}

function decodeEvent<T>(payload: string): { value: T } | null {
  try {
    return { value: JSON.parse(payload) as T };
  } catch {
    return null;
  }
}

/**
 * Read the task-progress dialect: `event:`/`data:` frames, a `[DONE]` payload
 * that ends the read, and no cursor. The assistant wire protocol does not
 * define this shape, and its strict reader refuses it.
 */
export async function* readTypedEvents<T>(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<T> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const next = await reader.read();
      if (next.done === true) return;
      buffer += decoder.decode(next.value, { stream: true });
      let boundary = buffer.indexOf(FRAME_TERMINATOR);
      while (boundary >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + FRAME_TERMINATOR.length);
        const payload = lastDataLine(frame);
        if (payload === TYPED_EVENT_DONE) return;
        const event = payload === null ? null : decodeEvent<T>(payload);
        if (event !== null) yield event.value;
        boundary = buffer.indexOf(FRAME_TERMINATOR);
      }
    }
  } finally {
    reader.releaseLock();
  }
}
