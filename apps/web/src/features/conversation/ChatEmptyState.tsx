"use client";

import { ThreadPrimitive } from "@assistant-ui/react";
import { motion } from "motion/react";

import suggestedQuestions from "@/features/conversation/data/suggestedQuestions.json";
import { cn } from "@/lib/utils/cn";
import { useSessionStore } from "@/state/useSessionStore";

type SuggestionsBySite = Record<string, readonly string[] | undefined>;

function suggestionsForSite(siteId: string): readonly string[] {
  const bank = suggestedQuestions as SuggestionsBySite;
  return bank[siteId] ?? bank["veupathdb"] ?? [];
}

function greetingForHour(hour: number): string {
  if (hour < 5) return "Still up?";
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

const suggestionEase = [0.22, 1, 0.36, 1] as const;

export function ChatEmptyState() {
  const siteId = useSessionStore((s) => s.selectedSite);
  const displayName = useSessionStore((s) => s.selectedSiteDisplayName);
  const suggestions = suggestionsForSite(siteId);
  const greeting = greetingForHour(new Date().getHours());

  return (
    <ThreadPrimitive.Empty>
      <div className="flex h-full flex-col items-center justify-center px-6 py-10 text-center">
        <motion.h1
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: suggestionEase, delay: 0.05 }}
          className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl"
        >
          {greeting}
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: suggestionEase, delay: 0.12 }}
          className="mt-2 max-w-md text-sm leading-relaxed text-muted-foreground"
        >
          Build and refine multi-step {displayName} search strategies with guided
          parameter selection and validation.
        </motion.p>

        {suggestions.length > 0 && (
          <div
            className={cn(
              "mt-8 w-full max-w-3xl",
              "flex gap-2.5 overflow-x-auto pb-1",
              "sm:grid sm:grid-cols-2 sm:overflow-visible",
              "[&::-webkit-scrollbar]:hidden",
            )}
            style={{ scrollbarWidth: "none" }}
          >
            {suggestions.map((prompt, i) => (
              <motion.div
                key={prompt}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{
                  delay: 0.18 + 0.06 * i,
                  duration: 0.4,
                  ease: suggestionEase,
                }}
                className="min-w-[240px] shrink-0 sm:min-w-0 sm:shrink"
              >
                <ThreadPrimitive.Suggestion
                  prompt={prompt}
                  send
                  className={cn(
                    "h-auto w-full whitespace-normal rounded-xl border border-border/60 bg-card/40 px-4 py-3",
                    "text-left text-[13px] leading-relaxed text-muted-foreground",
                    "transition-all duration-200",
                    "hover:-translate-y-0.5 hover:bg-card/80 hover:text-foreground hover:shadow-sm",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  )}
                >
                  {prompt}
                </ThreadPrimitive.Suggestion>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </ThreadPrimitive.Empty>
  );
}
