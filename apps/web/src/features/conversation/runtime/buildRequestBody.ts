import type { UIMessage } from "ai";

export interface BuildChatRequestBodyArgs {
  chatId: string;
  siteId: string;
  id: string;
  trigger: string;
  messages: UIMessage[];
  parentCheckpointId: string | null;
  baseBody: Record<string, unknown> | undefined;
}

export interface ChatRequestBodyShape {
  chatId: string;
  siteId: string;
  id: string;
  trigger: string;
  messages: UIMessage[];
  parentCheckpointId?: string;
  [key: string]: unknown;
}

export function buildChatRequestBody(
  args: BuildChatRequestBodyArgs,
): ChatRequestBodyShape {
  if (args.siteId.trim() === "") {
    throw new Error(
      "buildChatRequestBody: siteId is required but empty. "
      + "This means useSessionStore.selectedSite was not set before the chat "
      + "request was constructed.",
    );
  }
  return {
    ...(args.baseBody ?? {}),
    chatId: args.chatId,
    siteId: args.siteId,
    id: args.id,
    trigger: args.trigger,
    messages: args.messages,
    ...(args.parentCheckpointId !== null && {
      parentCheckpointId: args.parentCheckpointId,
    }),
  };
}
