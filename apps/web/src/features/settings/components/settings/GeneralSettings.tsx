"use client";

/**
 * GeneralSettings (Model tab) — default model, reasoning effort, and per-model tuning.
 */

import { useState, useCallback } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { ModelCatalogEntry, ModelProvider } from "@pathfinder/shared";
import { useSettingsStore, type ModelOverrides } from "@/state/useSettingsStore";
import { ModelPicker } from "@/lib/components/ModelPicker";
import { ReasoningToggle } from "@/lib/components/ReasoningToggle";
import { SettingsField } from "./SettingsField";

const PROVIDER_LABELS: Record<ModelProvider, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  google: "Google",
  ollama: "Ollama (Local)",
};

/** Providers that support a custom reasoning token budget. */
const BUDGET_PROVIDERS = new Set<ModelProvider>(["anthropic", "google"]);

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
  return String(n);
}

function defaultResponseTokens(contextSize: number): number {
  return Math.min(Math.floor(contextSize / 10), 8192);
}

function groupByProvider(models: ModelCatalogEntry[]) {
  const groups: Partial<Record<ModelProvider, ModelCatalogEntry[]>> = {};
  for (const m of models) {
    (groups[m.provider] ??= []).push(m);
  }
  return groups;
}

export function GeneralSettings() {
  const modelCatalog = useSettingsStore((s) => s.modelCatalog);
  const catalogDefault = useSettingsStore((s) => s.catalogDefault);
  const defaultModelId = useSettingsStore((s) => s.defaultModelId);
  const setDefaultModelId = useSettingsStore((s) => s.setDefaultModelId);
  const defaultReasoningEffort = useSettingsStore((s) => s.defaultReasoningEffort);
  const setDefaultReasoningEffort = useSettingsStore(
    (s) => s.setDefaultReasoningEffort,
  );
  const modelOverrides = useSettingsStore((s) => s.modelOverrides);
  const setModelOverride = useSettingsStore((s) => s.setModelOverride);

  const [tuningOpen, setTuningOpen] = useState(false);

  const selectedModel = modelCatalog.find((m) => m.id === defaultModelId);
  const supportsReasoning = selectedModel?.supportsReasoning ?? false;
  const serverDefaultId = catalogDefault;

  const groups = groupByProvider(modelCatalog);

  return (
    <div className="space-y-5">
      <SettingsField label="Default model">
        <ModelPicker
          models={modelCatalog}
          selectedModelId={defaultModelId}
          onSelect={(id) => setDefaultModelId(id || null)}
          serverDefaultId={serverDefaultId}
        />
        <p className="mt-1 text-xs text-muted-foreground">
          Used when no per-request model is chosen.
        </p>
      </SettingsField>

      <SettingsField label="Default reasoning effort">
        {supportsReasoning || !defaultModelId ? (
          <>
            <ReasoningToggle
              value={defaultReasoningEffort}
              onChange={setDefaultReasoningEffort}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              {defaultModelId
                ? "Applied when the selected model supports reasoning."
                : "Applied to all reasoning-capable models."}
            </p>
          </>
        ) : (
          <p className="text-xs text-muted-foreground">
            Selected model does not support reasoning.
          </p>
        )}
      </SettingsField>

      {/* Per-model tuning — collapsible */}
      <div className="border-t border-border pt-4">
        <button
          type="button"
          onClick={() => setTuningOpen((p) => !p)}
          className="flex w-full items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
        >
          {tuningOpen ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          Per-Model Tuning
        </button>

        {tuningOpen && (
          <div className="mt-3">
            <p className="mb-3 text-xs text-muted-foreground">
              Override context window, response budget, and reasoning budget per model.
              Leave empty to use defaults shown in gray.
            </p>

            <table className="w-full border-collapse text-xs">
              <thead>
                <tr className="border-b border-border text-left text-[10px] uppercase tracking-wider text-muted-foreground">
                  <th className="pb-1.5 pr-2 font-semibold">Model</th>
                  <th className="pb-1.5 px-1 font-semibold w-[80px]">Context</th>
                  <th className="pb-1.5 px-1 font-semibold w-[80px]">Response</th>
                  <th className="pb-1.5 pl-1 font-semibold w-[80px]">Reasoning</th>
                </tr>
              </thead>
              <tbody>
                {(Object.entries(groups) as [ModelProvider, ModelCatalogEntry[]][]).map(
                  ([provider, models]) => (
                    <ProviderGroup
                      key={provider}
                      provider={provider}
                      models={models}
                      overrides={modelOverrides}
                      onOverride={setModelOverride}
                    />
                  ),
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function ProviderGroup({
  provider,
  models,
  overrides,
  onOverride,
}: {
  provider: ModelProvider;
  models: ModelCatalogEntry[];
  overrides: Record<string, ModelOverrides>;
  onOverride: (
    id: string,
    field: keyof ModelOverrides,
    value: number | undefined,
  ) => void;
}) {
  return (
    <>
      <tr>
        <td
          colSpan={4}
          className="pt-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground"
        >
          {PROVIDER_LABELS[provider] ?? provider}
        </td>
      </tr>
      {models.map((m) => (
        <ModelRow
          key={m.id}
          model={m}
          overrides={overrides[m.id]}
          onOverride={onOverride}
        />
      ))}
    </>
  );
}

function ModelRow({
  model,
  overrides,
  onOverride,
}: {
  model: ModelCatalogEntry;
  overrides: ModelOverrides | undefined;
  onOverride: (
    id: string,
    field: keyof ModelOverrides,
    value: number | undefined,
  ) => void;
}) {
  const showBudget = model.supportsReasoning && BUDGET_PROVIDERS.has(model.provider);

  const handleChange = useCallback(
    (field: keyof ModelOverrides) => (e: React.ChangeEvent<HTMLInputElement>) => {
      const raw = e.target.value.trim();
      onOverride(
        model.id,
        field,
        raw === "" ? undefined : parseInt(raw, 10) || undefined,
      );
    },
    [model.id, onOverride],
  );

  const ctxDefault = model.contextSize;
  const respDefault = ctxDefault > 0 ? defaultResponseTokens(ctxDefault) : 8192;
  const budgetDefault = model.defaultReasoningBudget;

  return (
    <tr className="border-b border-border/50">
      <td className="py-1.5 pr-2">
        <span className="font-medium text-foreground">{model.name}</span>
        {!model.enabled && (
          <span className="ml-1.5 rounded bg-muted px-1 py-0.5 text-[9px] text-muted-foreground">
            no key
          </span>
        )}
      </td>
      <td className="py-1.5 px-1">
        <TuningInput
          value={overrides?.contextSize}
          placeholder={ctxDefault > 0 ? fmt(ctxDefault) : "auto"}
          onChange={handleChange("contextSize")}
        />
      </td>
      <td className="py-1.5 px-1">
        <TuningInput
          value={overrides?.responseTokens}
          placeholder={fmt(respDefault)}
          onChange={handleChange("responseTokens")}
        />
      </td>
      <td className="py-1.5 pl-1">
        {showBudget ? (
          <TuningInput
            value={overrides?.reasoningBudget}
            placeholder={budgetDefault > 0 ? fmt(budgetDefault) : "—"}
            onChange={handleChange("reasoningBudget")}
          />
        ) : (
          <span className="text-muted-foreground/40">—</span>
        )}
      </td>
    </tr>
  );
}

function TuningInput({
  value,
  placeholder,
  onChange,
}: {
  value: number | undefined;
  placeholder: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <input
      type="number"
      min={0}
      step={1024}
      value={value ?? ""}
      onChange={onChange}
      placeholder={placeholder}
      className="w-full rounded border border-border bg-transparent px-1.5 py-1 text-xs text-foreground placeholder:text-muted-foreground/40 focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring/30"
    />
  );
}
