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
 * The in-page link to what a finished task produced: the first turn from the
 * one that reported the outcome onward that carries prose or a figure.
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
  for (const message of messages.slice(from)) {
    if (message.parts.some((part) => carriesResult(part, figures))) {
      return `#${messageAnchorId(message.id)}`;
    }
  }
  return null;
}
