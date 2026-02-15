/**
 * ModelPicker — dropdown for selecting the LLM model per-request.
 *
 * Groups models by provider and disables entries whose provider has no API key.
 * Uses Radix DropdownMenu for accessible keyboard/mouse interactions.
 */

"use client";

import { useMemo } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChevronDown, Lock } from "lucide-react";
import type { ModelCatalogEntry, ModelProvider } from "@pathfinder/shared";

const PROVIDER_LABELS: Record<ModelProvider, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  google: "Google",
};

interface ModelPickerProps {
  models: ModelCatalogEntry[];
  selectedModelId: string | null;
  onSelect: (modelId: string) => void;
  disabled?: boolean;
  /** Server default model ID to show alongside "Server default" label. */
  serverDefaultId?: string | null;
}

export function ModelPicker({
  models,
  selectedModelId,
  onSelect,
  disabled,
  serverDefaultId,
}: ModelPickerProps) {
  const grouped = useMemo(() => {
    const groups: Record<string, ModelCatalogEntry[]> = {};
    for (const m of models) {
      (groups[m.provider] ??= []).push(m);
    }
    return groups;
  }, [models]);

  const selectedModel = useMemo(
    () => models.find((m) => m.id === selectedModelId),
    [models, selectedModelId],
  );

  const serverDefaultModel = useMemo(
    () => (serverDefaultId ? models.find((m) => m.id === serverDefaultId) : null),
    [models, serverDefaultId],
  );

  const displayName =
    selectedModel?.name ??
    (serverDefaultModel ? `${serverDefaultModel.name}` : "Default");

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          disabled={disabled || models.length === 0}
          className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          aria-label={`Select model: ${displayName}`}
        >
          <span className="max-w-[100px] truncate">{displayName}</span>
          <ChevronDown className="h-3 w-3 text-slate-400" aria-hidden />
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className="z-50 min-w-[200px] rounded-md border border-slate-200 bg-white p-1 shadow-lg"
          sideOffset={4}
          align="start"
        >
          {/* Server default option */}
          <DropdownMenu.Item
            onSelect={() => onSelect("")}
            className={`flex w-full cursor-pointer items-center justify-between gap-2 rounded px-3 py-1.5 text-left text-[12px] outline-none transition-colors hover:bg-slate-50 focus:bg-slate-50 ${
              !selectedModelId ? "font-semibold text-slate-900" : "text-slate-600"
            }`}
          >
            <span>Server default</span>
            {serverDefaultModel && (
              <span className="text-[10px] text-slate-400">
                {serverDefaultModel.name}
              </span>
            )}
          </DropdownMenu.Item>

          <DropdownMenu.Separator className="my-1 h-px bg-slate-100" />

          {Object.entries(grouped).map(([provider, providerModels]) => (
            <DropdownMenu.Group key={provider}>
              <DropdownMenu.Label className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                {PROVIDER_LABELS[provider as ModelProvider] ?? provider}
              </DropdownMenu.Label>
              {providerModels.map((m) => (
                <DropdownMenu.Item
                  key={m.id}
                  disabled={!m.enabled}
                  onSelect={() => m.enabled && onSelect(m.id)}
                  className={`flex w-full items-center justify-between gap-2 rounded px-3 py-1.5 text-left text-[12px] outline-none transition-colors ${
                    m.enabled
                      ? "cursor-pointer text-slate-700 hover:bg-slate-50 focus:bg-slate-50"
                      : "cursor-not-allowed text-slate-300"
                  } ${selectedModelId === m.id ? "bg-slate-50 font-semibold text-slate-900" : ""}`}
                >
                  <span className="truncate">{m.name}</span>
                  {!m.enabled && (
                    <Lock
                      className="h-3 w-3 flex-shrink-0 text-slate-300"
                      aria-label="API key not configured"
                    />
                  )}
                </DropdownMenu.Item>
              ))}
            </DropdownMenu.Group>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
