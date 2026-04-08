import { Brain } from "lucide-react";
import { useShallow } from "zustand/react/shallow";
import { useEngineStore } from "@/state/useEngineStore";

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
  const { provider, tier } = useEngineStore(useShallow((s) => ({ provider: s.provider, tier: s.tier })));

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
