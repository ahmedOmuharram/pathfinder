"use client";

import { ThreadPrimitive } from "@assistant-ui/react";

import suggestedQuestions from "@/features/chat/data/suggestedQuestions.json";
import { useSessionStore } from "@/state/useSessionStore";

type SuggestionsBySite = Record<string, readonly string[] | undefined>;

function suggestionsForSite(siteId: string): readonly string[] {
  const bank = suggestedQuestions as SuggestionsBySite;
  return bank[siteId] ?? bank["veupathdb"] ?? [];
}

export function ChatEmptyState() {
  const siteId = useSessionStore((s) => s.selectedSite);
  const displayName = useSessionStore((s) => s.selectedSiteDisplayName);
  const suggestions = suggestionsForSite(siteId);

  return (
    <ThreadPrimitive.Empty>
      <div className="flex h-full flex-col items-center justify-center px-6 py-10 text-center">
        <h2 className="mb-1 text-lg font-semibold tracking-tight text-foreground">
          {displayName}
        </h2>
        <p className="mb-6 max-w-md text-sm leading-relaxed text-muted-foreground">
          Build and refine multi-step VEuPathDB search strategies with guided
          parameter selection and validation.
        </p>
        <div className="grid w-full max-w-2xl grid-cols-1 gap-2 text-left">
          {suggestions.map((prompt) => (
            <ThreadPrimitive.Suggestion
              key={prompt}
              prompt={prompt}
              send
              className="rounded-lg border border-border bg-card px-4 py-3 text-left text-sm text-foreground shadow-xs transition-all duration-150 hover:-translate-y-px hover:border-ring/30 hover:shadow-sm active:translate-y-0"
            >
              &ldquo;{prompt}&rdquo;
            </ThreadPrimitive.Suggestion>
          ))}
        </div>
      </div>
    </ThreadPrimitive.Empty>
  );
}
