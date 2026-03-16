/**
 * ModelPicker -- button that opens the model catalog modal for selecting the LLM model.
 *
 * Displays the currently selected model name. Clicking opens the full
 * ModelCatalogModal where users can browse and select models.
 */

"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { ModelCatalogEntry } from "@pathfinder/shared";
import { ModelCatalogModal } from "@/lib/components/ModelCatalogModal";

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
  const [catalogOpen, setCatalogOpen] = useState(false);

  const selectedModel = models.find((m) => m.id === selectedModelId);
  const serverDefaultModel = serverDefaultId
    ? models.find((m) => m.id === serverDefaultId)
    : null;
  const displayName = selectedModel?.name ?? serverDefaultModel?.name ?? "Default";

  return (
    <>
      <button
        type="button"
        disabled={disabled || models.length === 0}
        onClick={() => setCatalogOpen(true)}
        className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-2 py-1 text-xs font-medium text-foreground transition hover:border-input hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
        aria-label={`Select model: ${displayName}`}
      >
        <span className="max-w-[100px] truncate">{displayName}</span>
        <ChevronDown className="h-3 w-3 text-muted-foreground" aria-hidden />
      </button>

      <ModelCatalogModal
        open={catalogOpen}
        onOpenChange={setCatalogOpen}
        onSelect={onSelect}
      />
    </>
  );
}
