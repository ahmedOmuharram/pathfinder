"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import type { ModelCatalogEntry } from "@pathfinder/shared";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  conversationDetailOptions,
  setConversationSupervisorModel,
} from "@/lib/api/conversations";
import { userPreferencesOptions } from "@/lib/api/me";
import { modelCatalogOptions } from "@/lib/api/models";

function modelLabel(
  models: ModelCatalogEntry[], modelId: string | null,
): string {
  if (modelId == null) return "Auto";
  return models.find((m) => m.id === modelId)?.name ?? modelId;
}

function providerLabel(id: string): string {
  if (id === "openai") return "OpenAI";
  if (id === "anthropic") return "Anthropic";
  if (id === "google") return "Google";
  if (id === "ollama") return "Ollama";
  return id;
}

function groupByProvider(
  models: ModelCatalogEntry[],
): [string, ModelCatalogEntry[]][] {
  const groups = new Map<string, ModelCatalogEntry[]>();
  for (const m of models) {
    const bucket = groups.get(m.provider) ?? [];
    bucket.push(m);
    groups.set(m.provider, bucket);
  }
  return [...groups.entries()];
}

export function OrchestratorPill({ conversationId }: { conversationId: string }) {
  const queryClient = useQueryClient();
  const [saving, setSaving] = useState(false);

  const { data: conversation } = useQuery(
    conversationDetailOptions(conversationId),
  );
  const { data: prefs } = useQuery(userPreferencesOptions());
  const { data: catalog } = useQuery(modelCatalogOptions());

  if (catalog == null) return null;
  const models = catalog.models.filter((m) => m.enabled !== false);
  const groups = groupByProvider(models);

  const conversationOverride = conversation?.supervisorModelId ?? null;
  const userDefault = prefs?.supervisorModelId ?? null;
  const effective = conversationOverride ?? userDefault;
  const usingOverride = conversationOverride !== null;

  async function update(modelId: string | null) {
    setSaving(true);
    try {
      await setConversationSupervisorModel(conversationId, modelId);
      await queryClient.invalidateQueries({
        queryKey: ["conversations", conversationId, "detail"],
      });
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to update orchestrator",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          disabled={saving}
          className="inline-flex items-center gap-1 rounded-full bg-muted/60 px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
        >
          <span>Orchestrator: {modelLabel(models, effective)}</span>
          {usingOverride && (
            <span className="text-[10px] text-primary">· chat</span>
          )}
          <ChevronDown className="h-3 w-3" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        className="max-h-[360px] w-[280px] overflow-y-auto"
      >
        <DropdownMenuItem
          onSelect={() => void update(null)}
          className={!usingOverride ? "bg-primary/15 text-primary" : undefined}
        >
          <div className="flex w-full items-center justify-between gap-2">
            <span>Use default</span>
            <span className="text-[10px] text-muted-foreground">
              {modelLabel(models, userDefault)}
            </span>
          </div>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {groups.map(([provider, list]) => (
          <DropdownMenuGroup key={provider}>
            <DropdownMenuLabel className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {providerLabel(provider)}
            </DropdownMenuLabel>
            {list.map((m) => (
              <DropdownMenuItem
                key={m.id}
                onSelect={() => void update(m.id)}
                className={
                  conversationOverride === m.id
                    ? "bg-primary/15 text-primary"
                    : undefined
                }
              >
                <div className="flex w-full items-center justify-between gap-2">
                  <span className="truncate">{m.name}</span>
                  {(m.inputPrice != null || m.outputPrice != null) && (
                    <span className="shrink-0 text-[10px] text-muted-foreground">
                      ${m.inputPrice?.toFixed(2) ?? "–"} / $
                      {m.outputPrice?.toFixed(2) ?? "–"}
                    </span>
                  )}
                </div>
              </DropdownMenuItem>
            ))}
          </DropdownMenuGroup>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
