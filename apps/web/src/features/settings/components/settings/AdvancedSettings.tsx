"use client";

/**
 * AdvancedSettings -- debug toggles, per-provider reasoning budgets, and strategy seeding.
 */

import { useState, useCallback } from "react";
import { useSettingsStore } from "@/state/useSettingsStore";
import { useSessionStore } from "@/state/useSessionStore";
import { Loader2, FlaskConical } from "lucide-react";
import { SettingsField } from "./SettingsField";

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
  const advancedReasoningBudgets = useSettingsStore((s) => s.advancedReasoningBudgets);
  const setAdvancedReasoningBudget = useSettingsStore(
    (s) => s.setAdvancedReasoningBudget,
  );
  const resetToDefaults = useSettingsStore((s) => s.resetToDefaults);
  const bumpAuthVersion = useSessionStore((s) => s.bumpAuthVersion);

  const [seeding, setSeeding] = useState(false);
  const [seedStatus, setSeedStatus] = useState<string | null>(null);

  const handleSeedExperiments = useCallback(async () => {
    setSeeding(true);
    setSeedStatus("Starting...");
    try {
      const response = await fetch("/api/v1/experiments/seed", {
        method: "POST",
        headers: { Accept: "text/event-stream" },
        credentials: "include",
      });
      if (!response.ok || !response.body) {
        setSeedStatus(`Failed: HTTP ${response.status}`);
        setSeeding(false);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          try {
            const data = JSON.parse(line.slice(5).trim());
            if (data.message) setSeedStatus(data.message);
          } catch {
            /* skip malformed */
          }
        }
      }
    } catch (err) {
      setSeedStatus(`Error: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setSeeding(false);
      bumpAuthVersion();
    }
  }, [bumpAuthVersion]);

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
        <div className="flex items-center gap-3">
          <button
            type="button"
            disabled={seeding}
            onClick={() => void handleSeedExperiments()}
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
          >
            {seeding ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <FlaskConical className="h-3.5 w-3.5" />
            )}
            {seeding ? "Seeding..." : "Seed Strategies"}
          </button>
          {seedStatus && (
            <span className="text-xs text-muted-foreground">{seedStatus}</span>
          )}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Seeds demo strategies and control sets across PlasmoDB, ToxoDB, CryptoDB, and
          TriTrypDB. Strategies appear in the sidebar; control sets are available in the
          Experiments tab.
        </p>
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
