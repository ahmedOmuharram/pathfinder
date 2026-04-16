"use client";

import { useAuiState } from "@assistant-ui/react";
import { Bot, Sparkles } from "lucide-react";
import type { ReactElement } from "react";

type ProviderSlug = "openai" | "anthropic" | "gemini" | "mistral" | "unknown";

interface ParsedModel {
  provider: ProviderSlug;
  model: string;
}

function parseModelString(raw: string): ParsedModel {
  const [first, ...rest] = raw.split(":");
  if (rest.length === 0) {
    return { provider: "unknown", model: first ?? raw };
  }
  const provider = (first ?? "").toLowerCase();
  const model = rest.join(":");
  if (provider === "openai" || provider === "anthropic") {
    return { provider, model };
  }
  if (provider === "gemini" || provider === "google") {
    return { provider: "gemini", model };
  }
  if (provider === "mistral") {
    return { provider: "mistral", model };
  }
  return { provider: "unknown", model };
}

function providerIcon(provider: ProviderSlug): ReactElement {
  switch (provider) {
    case "openai":
    case "gemini":
      return <Sparkles className="size-3" aria-hidden />;
    case "anthropic":
    case "mistral":
    case "unknown":
      return <Bot className="size-3" aria-hidden />;
  }
}

function providerLabel(provider: ProviderSlug): string {
  switch (provider) {
    case "openai":
      return "OpenAI";
    case "anthropic":
      return "Anthropic";
    case "gemini":
      return "Gemini";
    case "mistral":
      return "Mistral";
    case "unknown":
      return "Model";
  }
}

/**
 * Small badge displayed at the top of an assistant message showing the
 * model that produced it. Sourced from the message's
 * ``metadata.custom.model`` — which we stamp onto the LangChain
 * ``additional_kwargs.metadata`` in ``useLangGraphStream`` based on the
 * backend's ``data-phase-start.model`` event.
 */
export function ModelBadge(): ReactElement | null {
  const role = useAuiState((s) => s.message.role);
  const custom = useAuiState(
    (s) => s.message.metadata.custom as { model?: unknown } | undefined,
  );
  if (role !== "assistant") return null;
  const raw = custom?.model;
  if (typeof raw !== "string" || raw === "") return null;
  const parsed = parseModelString(raw);
  return (
    <div
      data-testid="model-badge"
      className="inline-flex items-center gap-1.5 self-start rounded-full border border-border bg-muted/50 px-2 py-0.5 text-[11px] text-muted-foreground"
    >
      {providerIcon(parsed.provider)}
      <span className="font-medium text-foreground">
        {providerLabel(parsed.provider)}
      </span>
      <span aria-hidden>·</span>
      <span className="font-mono">{parsed.model}</span>
    </div>
  );
}
