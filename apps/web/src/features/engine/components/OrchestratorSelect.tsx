"use client";

import type { ModelCatalogEntry } from "@pathfinder/shared";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  patchUserPreferences,
  userPreferencesOptions,
  userPreferencesQueryKey,
} from "@/lib/api/me";

const AUTO_VALUE = "__auto__";

function formatPrice(input?: number, output?: number): string {
  if (input == null && output == null) return "";
  const parts: string[] = [];
  if (input != null) parts.push(`$${input.toFixed(2)} in`);
  if (output != null) parts.push(`$${output.toFixed(2)} out`);
  return parts.join(" · ");
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

interface OrchestratorSelectProps {
  models: ModelCatalogEntry[];
}

export function OrchestratorSelect({ models }: OrchestratorSelectProps) {
  const queryClient = useQueryClient();
  const { data } = useQuery(userPreferencesOptions());
  const current = data?.supervisorModelId ?? null;

  const mutation = useMutation({
    mutationFn: (value: string | null) =>
      patchUserPreferences({ supervisorModelId: value }),
    onSuccess: (fresh) => {
      queryClient.setQueryData(userPreferencesQueryKey, fresh);
    },
    onError: (err) => {
      toast.error(
        err instanceof Error ? err.message : "Failed to update orchestrator",
      );
    },
  });

  const groups = groupByProvider(models.filter((m) => m.enabled !== false));

  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-muted-foreground">
        Orchestrator
      </label>
      <Select
        value={current ?? AUTO_VALUE}
        onValueChange={(raw) =>
          mutation.mutate(raw === AUTO_VALUE ? null : raw)
        }
        disabled={mutation.isPending}
      >
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Auto" />
        </SelectTrigger>
        <SelectContent className="max-h-[320px]">
          <SelectItem value={AUTO_VALUE}>
            Auto — smallest model of default provider
          </SelectItem>
          {groups.map(([provider, list]) => (
            <SelectGroup key={provider}>
              <SelectLabel>{providerLabel(provider)}</SelectLabel>
              {list.map((m) => {
                const price = formatPrice(m.inputPrice, m.outputPrice);
                return (
                  <SelectItem key={m.id} value={m.id}>
                    <span>{m.name}</span>
                    {price !== "" && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        {price}
                      </span>
                    )}
                  </SelectItem>
                );
              })}
            </SelectGroup>
          ))}
        </SelectContent>
      </Select>
      <p className="mt-1 text-[11px] text-muted-foreground">
        Routes decisions between phases. Smaller is usually fine.
      </p>
    </div>
  );
}
