"use client";

/**
 * ModelCatalogModal -- full browsable table of all available LLM models.
 *
 * Shows a filterable, sortable table with pricing, context size, and
 * provider grouping. Launched from the "Browse all models..." item in
 * the ModelPicker dropdown.
 */

import { useMemo, useState } from "react";
import { Check } from "lucide-react";
import type { ModelCatalogEntry, ModelProvider } from "@pathfinder/shared";
import { Modal } from "@/lib/components/Modal";
import { ProviderIcon } from "@/lib/components/ProviderIcon";
import { useSettingsStore } from "@/state/useSettingsStore";

import { formatCompactClean, formatPrice } from "@/lib/utils/format";
import { PROVIDER_TABS } from "@/lib/models/providerMeta";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type SortKey =
  | "name"
  | "contextSize"
  | "inputPrice"
  | "outputPrice"
  | "cachedInputPrice";
type SortDir = "asc" | "desc";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface ModelCatalogModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect?: (modelId: string) => void;
}

export function ModelCatalogModal({
  open,
  onOpenChange,
  onSelect,
}: ModelCatalogModalProps) {
  const catalog = useSettingsStore((s) => s.modelCatalog);
  const [providerFilter, setProviderFilter] = useState<"all" | ModelProvider>("all");
  const [sortKey, setSortKey] = useState<SortKey>("inputPrice");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  // Only show tabs for providers that have models
  const availableProviders = useMemo(() => {
    const providers = new Set(catalog.map((m) => m.provider));
    return PROVIDER_TABS.filter(
      (t) => t.key === "all" || providers.has(t.key as ModelProvider),
    );
  }, [catalog]);

  const filtered = useMemo(() => {
    const base =
      providerFilter === "all"
        ? catalog
        : catalog.filter((m) => m.provider === providerFilter);
    return [...base].sort((a, b) => {
      const valA = a[sortKey];
      const valB = b[sortKey];
      if (typeof valA === "string" && typeof valB === "string") {
        return sortDir === "asc" ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      const numA = valA as number;
      const numB = valB as number;
      return sortDir === "asc" ? numA - numB : numB - numA;
    });
  }, [catalog, providerFilter, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  function sortIndicator(key: SortKey): string {
    if (sortKey !== key) return "";
    return sortDir === "asc" ? " \u25B4" : " \u25BE";
  }

  return (
    <Modal
      open={open}
      onClose={() => onOpenChange(false)}
      title="Model Catalog"
      maxWidth="max-w-4xl"
      showCloseButton
    >
      <div className="flex flex-col max-h-[80vh]">
        {/* Header */}
        <div className="px-5 pt-5 pb-3">
          <h2 className="text-base font-semibold text-foreground">Model Catalog</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Compare models by pricing, context size, and capabilities.
          </p>
        </div>

        {/* Provider filter tabs */}
        <div className="px-5 pb-3 flex gap-1">
          {availableProviders.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setProviderFilter(tab.key)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                providerFilter === tab.key
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted/50 text-muted-foreground hover:bg-muted"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="flex-1 overflow-auto px-5 pb-2">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border/50 text-left text-muted-foreground">
                <th className="pb-2 pr-3 font-medium">
                  <button
                    type="button"
                    onClick={() => toggleSort("name")}
                    className="hover:text-foreground transition-colors"
                  >
                    Model{sortIndicator("name")}
                  </button>
                </th>
                <th className="pb-2 px-3 font-medium text-right">
                  <button
                    type="button"
                    onClick={() => toggleSort("contextSize")}
                    className="hover:text-foreground transition-colors"
                  >
                    Context{sortIndicator("contextSize")}
                  </button>
                </th>
                <th className="pb-2 px-3 font-medium text-right">
                  <button
                    type="button"
                    onClick={() => toggleSort("inputPrice")}
                    className="hover:text-foreground transition-colors"
                  >
                    Input $/MTok{sortIndicator("inputPrice")}
                  </button>
                </th>
                <th className="pb-2 px-3 font-medium text-right">
                  <button
                    type="button"
                    onClick={() => toggleSort("outputPrice")}
                    className="hover:text-foreground transition-colors"
                  >
                    Output $/MTok{sortIndicator("outputPrice")}
                  </button>
                </th>
                <th className="pb-2 px-3 font-medium text-right">
                  <button
                    type="button"
                    onClick={() => toggleSort("cachedInputPrice")}
                    className="hover:text-foreground transition-colors"
                  >
                    Cached $/MTok{sortIndicator("cachedInputPrice")}
                  </button>
                </th>
                <th className="pb-2 px-3 font-medium">Best For</th>
                {onSelect && <th className="pb-2 pl-3 font-medium w-16" />}
              </tr>
            </thead>
            <tbody>
              {filtered.map((model) => (
                <ModelRow
                  key={model.id}
                  model={model}
                  onSelect={onSelect}
                  onClose={() => onOpenChange(false)}
                />
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={onSelect ? 7 : 6}
                    className="py-8 text-center text-muted-foreground"
                  >
                    No models found for this provider.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-border/40 text-[10px] text-muted-foreground/60">
          Prices per 1M tokens (USD)
        </div>
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Row
// ---------------------------------------------------------------------------

function ModelRow({
  model,
  onSelect,
  onClose,
}: {
  model: ModelCatalogEntry;
  onSelect?: (modelId: string) => void;
  onClose: () => void;
}) {
  function handleSelect() {
    if (!onSelect || !model.enabled) return;
    onSelect(model.id);
    onClose();
  }

  return (
    <tr
      className={`border-b border-border/20 ${
        model.enabled ? "hover:bg-muted/30 transition-colors" : "opacity-50"
      }`}
    >
      {/* Model name + provider icon */}
      <td className="py-2.5 pr-3">
        <div className="flex items-center gap-2">
          <ProviderIcon provider={model.provider} size={14} />
          <div>
            <div className="font-medium text-foreground">{model.name}</div>
            {model.supportsReasoning && (
              <span className="text-[10px] text-amber-500/80">reasoning</span>
            )}
          </div>
        </div>
      </td>
      {/* Context */}
      <td className="py-2.5 px-3 text-right text-muted-foreground">
        {formatCompactClean(model.contextSize)}
      </td>
      {/* Input price */}
      <td className="py-2.5 px-3 text-right text-emerald-500/80">
        {formatPrice(model.inputPrice)}
      </td>
      {/* Output price */}
      <td className="py-2.5 px-3 text-right text-amber-500/80">
        {formatPrice(model.outputPrice)}
      </td>
      {/* Cached price */}
      <td className="py-2.5 px-3 text-right text-sky-500/80">
        {formatPrice(model.cachedInputPrice)}
      </td>
      {/* Best for / description */}
      <td className="py-2.5 px-3 text-muted-foreground max-w-[160px] truncate">
        {model.description || "\u2014"}
      </td>
      {/* Select */}
      {onSelect && (
        <td className="py-2.5 pl-3">
          <button
            type="button"
            disabled={!model.enabled}
            onClick={handleSelect}
            className="inline-flex items-center gap-1 rounded px-2 py-1 text-[10px] font-medium transition-colors bg-primary/10 text-primary hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Check className="h-3 w-3" />
            Select
          </button>
        </td>
      )}
    </tr>
  );
}
