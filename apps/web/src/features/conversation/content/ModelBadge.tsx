"use client";

import { useMessage, type ThreadMessage } from "@assistant-ui/react";
import type { ModelProvider } from "@pathfinder/shared";
import type { ReactElement } from "react";

import { ProviderIcon } from "@/lib/components/ProviderIcon";
import { PROVIDER_LABELS } from "@/lib/models/providerMeta";

interface ParsedModel {
  provider: ModelProvider | null;
  model: string;
}

function parseModelString(raw: string): ParsedModel {
  const [head, ...rest] = raw.split(":");
  const tail = rest.join(":");
  const slug = (head ?? "").toLowerCase();
  // Pydantic-AI identifies Google models with the ``google`` provider key;
  // ``gemini`` is the model family label. Treat both as Google for display.
  if (slug === "openai" || slug === "anthropic" || slug === "ollama" || slug === "mock") {
    return { provider: slug, model: tail };
  }
  if (slug === "google" || slug === "gemini") {
    return { provider: "google", model: tail };
  }
  return { provider: null, model: raw };
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
  const { provider, model } = parseModelString(raw);
  const label = provider !== null ? PROVIDER_LABELS[provider] : "Model";
  return (
    <div
      data-testid="model-badge"
      className="inline-flex items-center gap-1.5 self-start rounded-full border border-border bg-muted/50 px-2 py-0.5 text-[11px] text-muted-foreground"
    >
      {provider !== null && (
        <ProviderIcon provider={provider} size={12} className="shrink-0" />
      )}
      <span className="font-medium text-foreground">{label}</span>
      {model !== "" && (
        <>
          <span aria-hidden>·</span>
          <span className="font-mono">{model}</span>
        </>
      )}
    </div>
  );
}
