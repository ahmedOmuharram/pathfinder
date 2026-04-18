"use client";

import { useMessage, type ThreadMessage } from "@assistant-ui/react";
import { Bot, Sparkles } from "lucide-react";
import type { ReactElement } from "react";

type ProviderSlug = "openai" | "anthropic" | "gemini" | "mistral" | "unknown";

interface ParsedModel {
  provider: ProviderSlug;
  model: string;
}

function parseModelString(raw: string): ParsedModel {
  if (raw.includes(":")) {
    const [first, ...rest] = raw.split(":");
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
  const lower = raw.toLowerCase();
  if (lower.startsWith("gpt") || lower.startsWith("o1") || lower.startsWith("o3")) {
    return { provider: "openai", model: raw };
  }
  if (lower.startsWith("claude")) return { provider: "anthropic", model: raw };
  if (lower.startsWith("gemini")) return { provider: "gemini", model: raw };
  if (lower.startsWith("mistral")) return { provider: "mistral", model: raw };
  return { provider: "unknown", model: raw };
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

function selectLastPhaseModel(m: ThreadMessage): string | null {
  if (m.role !== "assistant") return null;
  for (let i = m.content.length - 1; i >= 0; i -= 1) {
    const part = m.content[i];
    if (part?.type !== "data") continue;
    if ("name" in part && part.name === "phase-start") {
      const data = part.data as { model?: unknown } | undefined;
      const model = data?.model;
      if (typeof model === "string" && model.length > 0) return model;
    }
  }
  return null;
}

export function ModelBadge(): ReactElement | null {
  const raw = useMessage({ optional: true, selector: selectLastPhaseModel });
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
