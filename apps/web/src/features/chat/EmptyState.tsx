"use client";

/**
 * Empty-state splash shown when a chat has no messages yet.
 *
 * Pulls site-specific starter prompts from `starter-prompts.ts` and renders them
 * as clickable cards. Clicking a card calls `sendMessage({ text })` on the same
 * AI SDK chat session used by the composer — the prompt flows through the
 * normal transport and the agent handles it like a typed user message. No
 * backend wire-format changes.
 *
 * Reads the active site from `useSessionStore` so prompts adapt as the user
 * switches between PlasmoDB / ToxoDB / etc. In experiment mode the site
 * selector is irrelevant so we use a single experiment-focused prompt list.
 */

import { MessageSquare, Sparkles } from "lucide-react";

import { useChatSessionContext } from "./approval/useChatContext";
import { getStarterPrompts } from "./starter-prompts";
import { useSessionStore } from "@/state/useSessionStore";

export function ChatEmptyState({
  mode,
  chatId,
}: {
  mode: "strategy" | "experiment";
  chatId: string;
}) {
  const session = useChatSessionContext();
  const siteId = useSessionStore((s) => s.selectedSite);
  const siteName = useSessionStore((s) => s.selectedSiteDisplayName);

  const hasChat = chatId.length > 0;

  if (!hasChat) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center text-muted-foreground">
        <MessageSquare className="h-10 w-10 opacity-40" />
        <p className="text-sm font-medium text-foreground">
          {mode === "strategy"
            ? "Pick a conversation in the sidebar or click \u201CNew Chat\u201D"
            : "Select a gene set to start chatting about experiments"}
        </p>
      </div>
    );
  }

  const prompts = getStarterPrompts(siteId, mode);
  const headline =
    mode === "strategy"
      ? `What gene set are you looking for?`
      : `Ask about this experiment`;
  const subline =
    mode === "strategy"
      ? `I can build search strategies on ${siteName}. Start with one of these or describe your own question.`
      : `I'll walk through metrics, gene lists, and suggest improvements.`;

  return (
    <div className="mx-auto flex h-full w-full max-w-3xl flex-col items-center justify-center gap-6 px-4 py-8">
      <div className="flex flex-col items-center gap-2 text-center">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Sparkles className="h-5 w-5" />
        </div>
        <h2 className="text-lg font-semibold text-foreground">{headline}</h2>
        <p className="max-w-md text-sm text-muted-foreground">{subline}</p>
      </div>

      {prompts.length > 0 && (
        <div className="grid w-full gap-2 sm:grid-cols-2">
          {prompts.map((p) => (
            <button
              key={p.title}
              type="button"
              onClick={() => {
                void session.sendMessage({ text: p.prompt });
              }}
              className="group flex flex-col items-start gap-1 rounded-lg border border-border bg-card px-3 py-2.5 text-left transition-colors hover:border-primary/40 hover:bg-accent"
            >
              <span className="text-sm font-medium text-foreground group-hover:text-accent-foreground">
                {p.title}
              </span>
              <span className="text-xs text-muted-foreground">
                {p.description}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
