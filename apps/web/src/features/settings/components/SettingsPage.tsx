"use client";

/**
 * SettingsPage — modal-based settings with General, Data, and Advanced tabs.
 */

import { useState, useCallback } from "react";
import { Modal } from "@/lib/components/Modal";
import { useSettingsStore } from "@/state/useSettingsStore";
import { ModelPicker } from "@/features/chat/components/ModelPicker";
import { ReasoningToggle } from "@/features/chat/components/ReasoningToggle";
import { listStrategies, deleteStrategy, deletePlanSession } from "@/lib/api/client";
import type { ReasoningEffort } from "@pathfinder/shared";
import { Loader2, Trash2 } from "lucide-react";

type Tab = "general" | "data" | "advanced";

interface SettingsPageProps {
  open: boolean;
  onClose: () => void;
  /** Site ID for scoped delete operations. */
  siteId: string;
  /** Refresh plan list after clearing plans. */
  onPlansCleared?: () => void;
  /** Refresh strategy list after clearing strategies. */
  onStrategiesCleared?: () => void;
}

export function SettingsPage({
  open,
  onClose,
  siteId,
  onPlansCleared,
  onStrategiesCleared,
}: SettingsPageProps) {
  const [tab, setTab] = useState<Tab>("general");

  return (
    <Modal open={open} onClose={onClose} title="Settings" maxWidth="max-w-lg">
      <div className="flex min-h-[340px] flex-col">
        {/* Tabs */}
        <div className="flex border-b border-slate-200 px-5">
          {(
            [
              { id: "general", label: "General" },
              { id: "data", label: "Data" },
              { id: "advanced", label: "Advanced" },
            ] as { id: Tab; label: string }[]
          ).map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`px-4 py-2.5 text-[12px] font-semibold transition-colors ${
                tab === t.id
                  ? "border-b-2 border-slate-900 text-slate-900"
                  : "text-slate-400 hover:text-slate-600"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {tab === "general" && <GeneralTab />}
          {tab === "data" && (
            <DataTab
              siteId={siteId}
              onPlansCleared={onPlansCleared}
              onStrategiesCleared={onStrategiesCleared}
            />
          )}
          {tab === "advanced" && <AdvancedTab />}
        </div>
      </div>
    </Modal>
  );
}

// General tab

function GeneralTab() {
  const modelCatalog = useSettingsStore((s) => s.modelCatalog);
  const catalogDefault = useSettingsStore((s) => s.catalogDefault);
  const defaultModelId = useSettingsStore((s) => s.defaultModelId);
  const setDefaultModelId = useSettingsStore((s) => s.setDefaultModelId);
  const defaultReasoningEffort = useSettingsStore((s) => s.defaultReasoningEffort);
  const setDefaultReasoningEffort = useSettingsStore(
    (s) => s.setDefaultReasoningEffort,
  );

  const selectedModel = modelCatalog.find((m) => m.id === defaultModelId);
  const supportsReasoning = selectedModel?.supportsReasoning ?? false;

  const serverDefaultId = catalogDefault;

  return (
    <div className="space-y-5">
      <SettingsField label="Default model">
        <ModelPicker
          models={modelCatalog}
          selectedModelId={defaultModelId}
          onSelect={(id) => setDefaultModelId(id || null)}
          serverDefaultId={serverDefaultId}
        />
        <p className="mt-1 text-[11px] text-slate-400">
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
            <p className="mt-1 text-[11px] text-slate-400">
              {defaultModelId
                ? "Applied when the selected model supports reasoning."
                : "Applied to all reasoning-capable models."}
            </p>
          </>
        ) : (
          <p className="text-[11px] text-slate-400">
            Selected model does not support reasoning.
          </p>
        )}
      </SettingsField>
    </div>
  );
}

// Data tab

function DataTab({
  siteId,
  onPlansCleared,
  onStrategiesCleared,
}: {
  siteId: string;
  onPlansCleared?: () => void;
  onStrategiesCleared?: () => void;
}) {
  const [clearing, setClearing] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const resetToDefaults = useSettingsStore((s) => s.resetToDefaults);

  const clearStrategies = useCallback(async () => {
    setClearing("strategies");
    setError(null);
    try {
      const all = await listStrategies(siteId);
      await Promise.allSettled(all.map((s) => deleteStrategy(s.id)));
      onStrategiesCleared?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clear strategies.");
    } finally {
      setClearing(null);
      setConfirmAction(null);
    }
  }, [siteId, onStrategiesCleared]);

  const clearPlans = useCallback(async () => {
    setClearing("plans");
    setError(null);
    try {
      // Plans are scoped to user; we need to fetch via the API.
      // Using a batch delete approach.
      const { requestJson } = await import("@/lib/api/http");
      const plans = await requestJson<{ id: string }[]>(
        `/api/v1/plans?siteId=${encodeURIComponent(siteId)}`,
      );
      await Promise.allSettled(plans.map((p) => deletePlanSession(p.id)));
      onPlansCleared?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clear plans.");
    } finally {
      setClearing(null);
      setConfirmAction(null);
    }
  }, [siteId, onPlansCleared]);

  const clearAll = useCallback(async () => {
    setClearing("all");
    setError(null);
    try {
      await clearStrategies();
      await clearPlans();
      resetToDefaults();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clear all data.");
    } finally {
      setClearing(null);
      setConfirmAction(null);
    }
  }, [clearStrategies, clearPlans, resetToDefaults]);

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
          {error}
        </div>
      )}

      <DangerAction
        label="Clear all plans"
        description="Delete all planning sessions for the current site."
        loading={clearing === "plans"}
        confirmed={confirmAction === "plans"}
        onConfirm={() => setConfirmAction("plans")}
        onExecute={clearPlans}
        onCancel={() => setConfirmAction(null)}
      />

      <DangerAction
        label="Clear all strategies"
        description="Delete all draft strategies for the current site."
        loading={clearing === "strategies"}
        confirmed={confirmAction === "strategies"}
        onConfirm={() => setConfirmAction("strategies")}
        onExecute={clearStrategies}
        onCancel={() => setConfirmAction(null)}
      />

      <DangerAction
        label="Clear all data"
        description="Delete all plans, strategies, and reset settings."
        loading={clearing === "all"}
        confirmed={confirmAction === "all"}
        onConfirm={() => setConfirmAction("all")}
        onExecute={clearAll}
        onCancel={() => setConfirmAction(null)}
      />
    </div>
  );
}

function DangerAction({
  label,
  description,
  loading,
  confirmed,
  onConfirm,
  onExecute,
  onCancel,
}: {
  label: string;
  description: string;
  loading: boolean;
  confirmed: boolean;
  onConfirm: () => void;
  onExecute: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-slate-200 px-3 py-2.5">
      <div>
        <div className="text-[12px] font-medium text-slate-700">{label}</div>
        <div className="text-[11px] text-slate-400">{description}</div>
      </div>
      {confirmed ? (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="rounded-md border border-slate-200 px-2 py-1 text-[11px] font-medium text-slate-600 transition hover:bg-slate-50 disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onExecute}
            disabled={loading}
            className="inline-flex items-center gap-1 rounded-md bg-red-600 px-2 py-1 text-[11px] font-medium text-white transition hover:bg-red-700 disabled:opacity-60"
          >
            {loading && <Loader2 className="h-3 w-3 animate-spin" />}
            Confirm
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={onConfirm}
          className="inline-flex items-center gap-1 rounded-md border border-red-200 px-2 py-1 text-[11px] font-medium text-red-600 transition hover:bg-red-50"
        >
          <Trash2 className="h-3 w-3" />
          {label}
        </button>
      )}
    </div>
  );
}

// Advanced tab

function AdvancedTab() {
  const showRawToolCalls = useSettingsStore((s) => s.showRawToolCalls);
  const setShowRawToolCalls = useSettingsStore((s) => s.setShowRawToolCalls);
  const advancedReasoningBudgets = useSettingsStore((s) => s.advancedReasoningBudgets);
  const setAdvancedReasoningBudget = useSettingsStore(
    (s) => s.setAdvancedReasoningBudget,
  );
  const resetToDefaults = useSettingsStore((s) => s.resetToDefaults);

  const providers = [
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
  ];

  return (
    <div className="space-y-5">
      <SettingsField label="Show raw tool calls in chat">
        <label className="inline-flex cursor-pointer items-center gap-2 text-[12px]">
          <input
            type="checkbox"
            checked={showRawToolCalls}
            onChange={(e) => setShowRawToolCalls(e.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
          />
          <span className="text-slate-600">
            Display raw JSON tool calls in the chat log
          </span>
        </label>
      </SettingsField>

      <SettingsField label="Per-provider reasoning token budgets">
        <div className="space-y-2">
          {providers.map((p) => (
            <div key={p.id} className="flex items-center gap-3">
              <label
                htmlFor={`budget-${p.id}`}
                className="w-20 text-[11px] font-medium text-slate-600"
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
                className="w-24 rounded-md border border-slate-200 px-2 py-1 text-[12px] text-slate-700"
              />
              <span className="text-[10px] text-slate-400">{p.hint}</span>
            </div>
          ))}
        </div>
      </SettingsField>

      <div className="border-t border-slate-100 pt-4">
        <button
          type="button"
          onClick={resetToDefaults}
          className="rounded-md border border-slate-200 px-3 py-1.5 text-[11px] font-medium text-slate-600 transition hover:bg-slate-50"
        >
          Reset all settings to defaults
        </button>
      </div>
    </div>
  );
}

// Shared layout

function SettingsField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        {label}
      </div>
      {children}
    </div>
  );
}
