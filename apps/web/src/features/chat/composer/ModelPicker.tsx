"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";

import { useHasHydrated } from "@/lib/hooks/useHasHydrated";
import { modelCatalogOptions } from "@/lib/api/models";
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

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-md border border-border bg-card px-2.5 py-1 text-xs font-medium hover:bg-accent"
      >
        <span className="text-muted-foreground">{tierLabel}</span>
        <span className="text-foreground">{currentLabel}</span>
        <ChevronDown className="h-3 w-3 opacity-60" />
      </button>

      {open && (
        <>
          <button
            type="button"
            aria-label="Close menu"
            className="fixed inset-0 z-10 cursor-default"
            onClick={() => setOpen(false)}
          />
          <div className="absolute right-0 z-20 mt-1 w-64 rounded-md border border-border bg-card p-1 shadow-lg">
            <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Quick swap (planning phase)
            </div>
            {(catalog?.models ?? []).map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => {
                  setPhaseModel("planning", m.id);
                  setOpen(false);
                }}
                className={`flex w-full flex-col items-start rounded px-2 py-1.5 text-left text-xs transition-colors ${
                  m.id === planningModelId
                    ? "bg-accent text-accent-foreground"
                    : "hover:bg-accent/50"
                }`}
              >
                <span className="font-medium">{m.name}</span>
                <span className="text-[10px] text-muted-foreground">
                  {m.provider} · {m.model}
                </span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
