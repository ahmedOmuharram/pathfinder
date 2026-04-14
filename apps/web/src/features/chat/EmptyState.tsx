"use client";

import { MessageSquare, Sparkles } from "lucide-react";

import { Suggestion } from "@/components/ai-elements/suggestion";
import { useSessionStore } from "@/state/useSessionStore";

import { useChatSessionContext } from "./approval/useChatContext";
import { getStarterPrompts } from "./starter-prompts";

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

  if (mode === "experiment" && chatId.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center text-muted-foreground">
        <MessageSquare className="h-10 w-10 opacity-40" />
        <p className="text-sm font-medium text-foreground">
          Select a gene set to start chatting about experiments
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
            <Suggestion
              key={p.title}
              suggestion={p.prompt}
              onClick={(text) => {
                void session.sendMessage({ text });
              }}
              variant="outline"
              size="default"
              className="group h-auto flex-col items-start gap-1 whitespace-normal rounded-lg border-border bg-card px-3 py-2.5 text-left hover:border-primary/40 hover:bg-accent"
            >
              <span className="w-full text-sm font-medium text-foreground group-hover:text-accent-foreground">
                {p.title}
              </span>
              <span className="w-full text-xs text-muted-foreground">
                {p.description}
              </span>
            </Suggestion>
          ))}
        </div>
      )}
    </div>
  );
}
