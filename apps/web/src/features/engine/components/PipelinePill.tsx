"use client";

import { useQuery } from "@tanstack/react-query";
import { Brain } from "lucide-react";

import {
  DEFAULT_PIPELINE_CONFIG,
  userPreferencesOptions,
} from "@/lib/api/me";

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  google: "Google",
  ollama: "Ollama",
};

const TIER_LABELS: Record<string, string> = {
  quality: "Quality",
  balanced: "Balanced",
  fast: "Fast",
  custom: "Custom",
};

interface PipelinePillProps {
  onClick: () => void;
}

export function PipelinePill({ onClick }: PipelinePillProps) {
  const { data } = useQuery({
    ...userPreferencesOptions(),
    select: (prefs) => {
      const cfg = prefs.pipelineConfig ?? DEFAULT_PIPELINE_CONFIG;
      return { provider: cfg.provider, tier: cfg.tier };
    },
  });
  const provider = data?.provider ?? DEFAULT_PIPELINE_CONFIG.provider;
  const tier = data?.tier ?? DEFAULT_PIPELINE_CONFIG.tier;

  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
    >
      <Brain className="h-3.5 w-3.5" />
      {PROVIDER_LABELS[provider] ?? provider} · {TIER_LABELS[tier] ?? tier}
    </button>
  );
}
