"use client";

/**
 * AdvancedSettings -- debug toggles, per-provider reasoning budgets, and strategy seeding.
 */

import { useState, useCallback } from "react";
import { useSettingsStore } from "@/state/useSettingsStore";
import { useSessionStore } from "@/state/useSessionStore";
import { seedExperiments } from "@/lib/api/experiments";
import { Loader2, FlaskConical, Database } from "lucide-react";
import { SettingsField } from "./SettingsField";

const SEED_DATABASES = [
  { id: "plasmodb", label: "PlasmoDB", description: "P. falciparum malaria" },
  { id: "toxodb", label: "ToxoDB", description: "T. gondii toxoplasmosis" },
  { id: "cryptodb", label: "CryptoDB", description: "Cryptosporidium" },
  {
    id: "piroplasmadb",
    label: "PiroplasmaDB",
    description: "B. bovis babesiosis",
  },
  {
    id: "tritrypdb",
    label: "TriTrypDB",
    description: "Leishmania & Trypanosoma",
  },
  {
    id: "fungidb",
    label: "FungiDB",
    description: "A. fumigatus aspergillosis",
  },
  {
    id: "vectorbase",
    label: "VectorBase",
    description: "A. gambiae mosquito",
  },
  { id: "giardiadb", label: "GiardiaDB", description: "Giardia lamblia" },
  {
    id: "amoebadb",
    label: "AmoebaDB",
    description: "E. histolytica amoeba",
  },
  {
    id: "microsporidiadb",
    label: "MicrosporidiaDB",
    description: "E. cuniculi microsporidia",
  },
  {
    id: "hostdb",
    label: "HostDB",
    description: "Human host immune response",
  },
  { id: "veupathdb", label: "VEuPathDB", description: "Cross-species portal" },
  { id: "orthomcl", label: "OrthoMCL", description: "Ortholog groups" },
] as const;

const PROVIDERS = [
  {
    id: "openai",
    label: "OpenAI",
    hint: "Budget tokens for reasoning models (o-series, gpt-5)",
    defaultBudget: 8192,
  },
  {
    id: "anthropic",
    label: "Anthropic",
    hint: "Budget tokens for Claude extended thinking",
    defaultBudget: 8192,
  },
  {
    id: "google",
    label: "Google",
    hint: "Budget tokens for Gemini thinking config",
    defaultBudget: 8192,
  },
] as const;

export function AdvancedSettings() {
  const showRawToolCalls = useSettingsStore((s) => s.showRawToolCalls);
  const setShowRawToolCalls = useSettingsStore((s) => s.setShowRawToolCalls);
  const syncDeleteToWdk = useSettingsStore((s) => s.syncDeleteToWdk);
  const setSyncDeleteToWdk = useSettingsStore((s) => s.setSyncDeleteToWdk);
  const advancedReasoningBudgets = useSettingsStore((s) => s.advancedReasoningBudgets);
  const setAdvancedReasoningBudget = useSettingsStore(
    (s) => s.setAdvancedReasoningBudget,
  );
  const resetToDefaults = useSettingsStore((s) => s.resetToDefaults);
  const bumpAuthVersion = useSessionStore((s) => s.bumpAuthVersion);

  const [seedingDb, setSeedingDb] = useState<string | null>(null);
  const [seedStatus, setSeedStatus] = useState<string | null>(null);

  const handleSeed = useCallback(
    async (siteId?: string) => {
      setSeedingDb(siteId ?? "all");
      setSeedStatus("Starting...");
      try {
        await seedExperiments((message) => setSeedStatus(message), siteId);
      } catch (err) {
        setSeedStatus(`Error: ${err instanceof Error ? err.message : "Unknown error"}`);
      } finally {
        setSeedingDb(null);
        bumpAuthVersion();
      }
    },
    [bumpAuthVersion],
  );

  return (
    <div className="space-y-5">
      <SettingsField label="Show raw tool calls in chat">
        <label className="inline-flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={showRawToolCalls}
            onChange={(e) => setShowRawToolCalls(e.target.checked)}
            className="h-4 w-4 rounded border-input text-foreground focus:ring-ring"
          />
          <span className="text-muted-foreground">
            Display raw JSON tool calls in the chat log
          </span>
        </label>
      </SettingsField>

      <SettingsField label="Sync strategy deletion to WDK">
        <label className="inline-flex cursor-pointer items-center gap-2 text-sm">
          <input
            data-testid="sync-delete-to-wdk-checkbox"
            type="checkbox"
            checked={syncDeleteToWdk}
            onChange={(e) => setSyncDeleteToWdk(e.target.checked)}
            className="h-4 w-4 rounded border-input text-foreground focus:ring-ring"
          />
          <span className="text-muted-foreground">
            When enabled, deleting a strategy also removes it from VEuPathDB
          </span>
        </label>
      </SettingsField>

      <SettingsField label="Per-provider reasoning token budgets">
        <div className="space-y-2">
          {PROVIDERS.map((p) => (
            <div key={p.id} className="flex items-center gap-3">
              <label
                htmlFor={`budget-${p.id}`}
                className="w-20 text-xs font-medium text-muted-foreground"
              >
                {p.label}
              </label>
              <input
                id={`budget-${p.id}`}
                type="number"
                min={0}
                step={1024}
                value={advancedReasoningBudgets[p.id] ?? p.defaultBudget}
                onChange={(e) =>
                  setAdvancedReasoningBudget(p.id, parseInt(e.target.value, 10) || 0)
                }
                className="w-24 rounded-md border border-border px-2 py-1 text-sm text-foreground"
              />
              <span className="text-xs text-muted-foreground">{p.hint}</span>
            </div>
          ))}
        </div>
      </SettingsField>

      <SettingsField label="Seed demo strategies">
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <button
              type="button"
              disabled={seedingDb !== null}
              onClick={() => void handleSeed()}
              className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
            >
              {seedingDb === "all" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <FlaskConical className="h-3.5 w-3.5" />
              )}
              {seedingDb === "all" ? "Seeding All..." : "Seed All Databases"}
            </button>
            {seedStatus && (
              <span className="text-xs text-muted-foreground">{seedStatus}</span>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            {SEED_DATABASES.map((db) => (
              <button
                key={db.id}
                type="button"
                disabled={seedingDb !== null}
                onClick={() => void handleSeed(db.id)}
                className="flex items-start gap-2 rounded-md border border-border px-2.5 py-2 text-left text-xs transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
              >
                {seedingDb === db.id ? (
                  <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin text-muted-foreground" />
                ) : (
                  <Database className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                )}
                <div className="min-w-0">
                  <div className="font-medium text-foreground">{db.label}</div>
                  <div className="truncate text-muted-foreground">{db.description}</div>
                </div>
              </button>
            ))}
          </div>

          <p className="text-xs text-muted-foreground">
            Seeds demo strategies and control sets for the selected database. Strategies
            appear in the sidebar; control sets are available in the Experiments tab.
          </p>
        </div>
      </SettingsField>

      <div className="border-t border-border pt-4">
        <button
          type="button"
          onClick={resetToDefaults}
          className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition hover:bg-muted"
        >
          Reset all settings to defaults
        </button>
      </div>
    </div>
  );
}
