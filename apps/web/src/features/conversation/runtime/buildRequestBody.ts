import type { UIMessage } from "ai";

export interface BuildChatRequestBodyArgs {
  conversationId: string;
  siteId: string;
  id: string;
  trigger: string;
  messages: UIMessage[];
  baseBody: Record<string, unknown> | undefined;
}

export interface ChatRequestBodyShape {
  conversationId: string;
  siteId: string;
  id: string;
  trigger: string;
  messages: UIMessage[];
  [key: string]: unknown;
}

export function buildChatRequestBody(
  args: BuildChatRequestBodyArgs,
): ChatRequestBodyShape {
  if (args.siteId.trim() === "") {
    throw new Error(
      "buildChatRequestBody: siteId is required but empty. " +
        "This means useSessionStore.selectedSite was not set before the chat " +
        "request was constructed.",
    );
  }
  return {
    ...(args.baseBody ?? {}),
    conversationId: args.conversationId,
    siteId: args.siteId,
    id: args.id,
    trigger: args.trigger,
    messages: args.messages,
  };
}
