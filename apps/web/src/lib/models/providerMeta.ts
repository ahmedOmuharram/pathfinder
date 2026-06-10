/**
 * Provider display metadata -- single source of truth.
 *
 * Consumed by GeneralSettings (PROVIDER_LABELS), ModelCatalogModal (PROVIDER_TABS),
 * and anywhere else that needs human-readable provider names.
 */

import type { ModelProvider } from "@pathfinder/shared";

export interface ParsedModel {
  provider: ModelProvider | null;
  model: string;
}

/** Split a ``provider:model`` id into a typed provider + model name. */
export function parseModelString(raw: string): ParsedModel {
  const [head, ...rest] = raw.split(":");
  const tail = rest.join(":");
  const slug = (head ?? "").toLowerCase();
  if (
    slug === "openai" ||
    slug === "anthropic" ||
    slug === "ollama" ||
    slug === "mock"
  ) {
    return { provider: slug, model: tail };
  }
  if (slug === "google" || slug === "gemini") {
    return { provider: "google", model: tail };
  }
  return { provider: null, model: raw };
}

/** Providers with no brand logo — rendered as a shimmer instead. */
export function isLocalProvider(provider: ModelProvider | null): boolean {
  return provider === null || provider === "ollama" || provider === "mock";
}

/** Human-readable labels for each provider. */
export const PROVIDER_LABELS: Record<ModelProvider, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  google: "Google",
  ollama: "Ollama (Local)",
  mock: "Mock",
};

/**
 * Ordered tabs for provider filtering UI (e.g. ModelCatalogModal).
 *
 * Uses shorter labels than PROVIDER_LABELS since they appear as tabs.
 */
export const PROVIDER_TABS: { key: "all" | ModelProvider; label: string }[] = [
  { key: "all", label: "All" },
  { key: "openai", label: "OpenAI" },
  { key: "anthropic", label: "Anthropic" },
  { key: "google", label: "Google" },
  { key: "ollama", label: "Ollama" },
];
