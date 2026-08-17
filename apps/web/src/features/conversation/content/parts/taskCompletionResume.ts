import type { TaskEventChunk } from "./taskLiveState";

/**
 * Pass a task's chunks through and report once that the task is settled.
 *
 * A turn that defers to a durable task ends its own response at the
 * interrupt, so the rest of the turn is written only after the task finishes
 * and an open page needs this signal to read it. The terminal chunk is the
 * early signal; a stream opened while the task was running can end without
 * one, so the end of the stream counts too.
 */
export async function* announceTaskCompletion(
  chunks: AsyncIterable<TaskEventChunk>,
  onComplete: () => void,
): AsyncIterable<TaskEventChunk> {
  let announced = false;
  const announce = (): void => {
    if (announced) return;
    announced = true;
    onComplete();
  };
  try {
    for await (const chunk of chunks) {
      if (chunk.type === "custom" && chunk.kind === "data-task-completed") {
        announce();
      }
      yield chunk;
    }
  } finally {
    announce();
  }
}
