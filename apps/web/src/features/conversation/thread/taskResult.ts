import { z } from "zod";

interface PartLike {
  type: string;
  text?: string | undefined;
  data?: unknown;
}

interface MessageLike {
  id: string;
  parts: readonly PartLike[];
}

const completedSchema = z.object({ taskId: z.string().min(1) });

/** The DOM id of the message a link can jump to. */
export function messageAnchorId(messageId: string): string {
  return `message-${messageId}`;
}

function completesTask(part: PartLike, taskId: string): boolean {
  if (part.type !== "data-task-completed") return false;
  const parsed = completedSchema.safeParse(part.data);
  return parsed.success && parsed.data.taskId === taskId;
}

function carriesResult(part: PartLike, figures: ReadonlySet<string>): boolean {
  if (part.type === "text") return (part.text ?? "").trim() !== "";
  return figures.has(part.type);
}

/**
 * The in-page link to what a finished task produced: the first prose or figure
 * written after the outcome was reported. A turn writes the answer into the
 * message that started the task, so parts before the outcome belong to the
 * request and never to its result.
 */
export function taskResultHref(
  messages: readonly MessageLike[],
  taskId: string,
  figures: ReadonlySet<string>,
): string | null {
  const from = messages.findIndex((message) =>
    message.parts.some((part) => completesTask(part, taskId)),
  );
  if (from < 0) return null;
  for (const [offset, message] of messages.slice(from).entries()) {
    const parts =
      offset === 0
        ? message.parts.slice(
            message.parts.findIndex((part) => completesTask(part, taskId)) + 1,
          )
        : message.parts;
    if (parts.some((part) => carriesResult(part, figures))) {
      return `#${messageAnchorId(message.id)}`;
    }
  }
  return null;
}
