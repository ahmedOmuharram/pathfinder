import type { ModelCatalogEntry, ModelProvider, PipelinePhase } from "@pathfinder/shared";
import { cn } from "@/lib/utils/cn";
import { Zap } from "lucide-react";
import { useState } from "react";

const PROVIDER_TABS: { value: ModelProvider | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "google", label: "Google" },
  { value: "ollama", label: "Ollama" },
];

interface CatalogPanelProps {
  models: ModelCatalogEntry[];
  selectedPhase: PipelinePhase | null;
  activeModelId: string | null;
  onSelectModel: (modelId: string) => void;
}

export function CatalogPanel({
  models,
  selectedPhase,
  activeModelId,
  onSelectModel,
}: CatalogPanelProps) {
  const [providerFilter, setProviderFilter] = useState<ModelProvider | "all">("all");

  const filtered = providerFilter === "all"
    ? models
    : models.filter((m) => m.provider === providerFilter);

  const isInteractive = selectedPhase !== null;

  return (
    <div className="flex h-full flex-col">
      {/* Provider tabs */}
      <div className="flex gap-1 border-b px-4 pt-4 pb-2">
        {PROVIDER_TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            onClick={() => setProviderFilter(tab.value)}
            className={cn(
              "rounded-md px-3 py-1 text-xs font-medium transition-colors",
              providerFilter === tab.value
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-muted-foreground">
              <th className="py-2 font-medium">Model</th>
              <th className="py-2 font-medium">Input $/1M</th>
              <th className="py-2 font-medium">Output $/1M</th>
              <th className="py-2 font-medium">Cached $/1M</th>
              <th className="py-2 font-medium">Context</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((model) => {
              const isActive = model.id === activeModelId;
              return (
                <tr
                  key={model.id}
                  onClick={() => isInteractive && onSelectModel(model.id)}
                  className={cn(
                    "border-b transition-colors",
                    isInteractive && "cursor-pointer hover:bg-accent/50",
                    isActive && "bg-primary/5 font-medium",
                    model.enabled === false && "opacity-40",
                  )}
                >
                  <td className="py-2">
                    <div className="flex items-center gap-1.5">
                      {model.name}
                      {model.supportsReasoning === true && (
                        <Zap className="h-3 w-3 text-amber-500" />
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground">{model.description}</div>
                  </td>
                  <td className="py-2">${(model.inputPrice ?? 0).toFixed(2)}</td>
                  <td className="py-2">${(model.outputPrice ?? 0).toFixed(2)}</td>
                  <td className="py-2">${(model.cachedInputPrice ?? 0).toFixed(2)}</td>
                  <td className="py-2">
                    {(model.contextSize ?? 0) > 0
                      ? `${((model.contextSize ?? 0) / 1_000_000).toFixed(1)}M`
                      : "\u2014"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
