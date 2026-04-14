"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";

import {
  ModelSelector,
  ModelSelectorContent,
  ModelSelectorEmpty,
  ModelSelectorGroup,
  ModelSelectorInput,
  ModelSelectorItem,
  ModelSelectorList,
  ModelSelectorName,
  ModelSelectorTrigger,
} from "@/components/ai-elements/model-selector";
import { Button } from "@/components/ui/button";
import { modelCatalogOptions } from "@/lib/api/models";
import { useHasHydrated } from "@/lib/hooks/useHasHydrated";
import { useEngineStore } from "@/state/useEngineStore";

const TIER_LABEL: Record<string, string> = {
  fast: "Fast",
  balanced: "Balanced",
  smart: "Smart",
  opus: "Opus",
  custom: "Custom",
};

export function ModelPicker() {
  const tier = useEngineStore((s) => s.tier);
  const planningModelId = useEngineStore((s) => s.phases.planning.modelId);
  const setPhaseModel = useEngineStore((s) => s.setPhaseModel);

  const { data: catalog } = useQuery(modelCatalogOptions());
  const [open, setOpen] = useState(false);

  const hasHydrated = useHasHydrated();
  const currentModel = catalog?.models.find((m) => m.id === planningModelId);
  const currentLabel = hasHydrated
    ? (currentModel?.name ?? planningModelId)
    : "";
  const tierLabel = hasHydrated ? (TIER_LABEL[tier] ?? tier) : "";

  const allModels = catalog?.models ?? [];
  const modelsByProvider = new Map<string, typeof allModels>();
  for (const m of allModels) {
    const list = modelsByProvider.get(m.provider) ?? [];
    list.push(m);
    modelsByProvider.set(m.provider, list);
  }

  return (
    <ModelSelector open={open} onOpenChange={setOpen}>
      <ModelSelectorTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2 text-xs font-medium">
          <span className="text-muted-foreground">{tierLabel}</span>
          <span className="text-foreground">{currentLabel}</span>
          <ChevronDown className="h-3 w-3 opacity-60" />
        </Button>
      </ModelSelectorTrigger>
      <ModelSelectorContent>
        <ModelSelectorInput placeholder="Search models…" />
        <ModelSelectorList>
          <ModelSelectorEmpty>No models found.</ModelSelectorEmpty>
          {[...modelsByProvider.entries()].map(([provider, models]) => (
            <ModelSelectorGroup key={provider} heading={provider}>
              {models.map((m) => (
                <ModelSelectorItem
                  key={m.id}
                  value={`${m.id} ${m.name} ${m.provider}`}
                  disabled={!m.enabled}
                  onSelect={() => {
                    setPhaseModel("planning", m.id);
                    setOpen(false);
                  }}
                  data-active={m.id === planningModelId || undefined}
                >
                  <ModelSelectorName>{m.name}</ModelSelectorName>
                  <span className="text-xs text-muted-foreground">{m.model}</span>
                </ModelSelectorItem>
              ))}
            </ModelSelectorGroup>
          ))}
        </ModelSelectorList>
      </ModelSelectorContent>
    </ModelSelector>
  );
}
