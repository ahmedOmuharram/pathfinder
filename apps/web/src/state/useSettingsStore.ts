/**
 * User settings store — persisted to localStorage.
 *
 * Stores default model/provider/reasoning preferences and
 * advanced per-provider budgets.
 */

import { create } from "zustand";
import type { ModelCatalogEntry, ReasoningEffort } from "@pathfinder/shared";

const STORAGE_KEY = "pathfinder-settings";

export interface SettingsState {
  /** Default model catalog ID (e.g. "openai/gpt-5"). null = use server default. */
  defaultModelId: string | null;
  /** Default reasoning effort. */
  defaultReasoningEffort: ReasoningEffort;
  /** Per-provider reasoning token budgets (advanced). */
  advancedReasoningBudgets: Record<string, number>;
  /** Show raw tool calls in chat (advanced). */
  showRawToolCalls: boolean;

  /** Cached model catalog from the API. */
  modelCatalog: ModelCatalogEntry[];
  /** Server-provided defaults per mode. */
  catalogDefaults: { execute: string; plan: string } | null;

  // Actions
  setDefaultModelId: (id: string | null) => void;
  setDefaultReasoningEffort: (effort: ReasoningEffort) => void;
  setAdvancedReasoningBudget: (provider: string, budget: number) => void;
  setShowRawToolCalls: (show: boolean) => void;
  setModelCatalog: (
    models: ModelCatalogEntry[],
    defaults: { execute: string; plan: string },
  ) => void;
  resetToDefaults: () => void;
}

function loadPersistedSettings(): Partial<SettingsState> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as Partial<SettingsState>;
  } catch {
    return {};
  }
}

function persist(partial: Partial<SettingsState>) {
  if (typeof window === "undefined") return;
  const current = loadPersistedSettings();
  const merged = { ...current, ...partial };
  // Only persist user-editable fields, not the cached catalog.
  const {
    defaultModelId,
    defaultReasoningEffort,
    advancedReasoningBudgets,
    showRawToolCalls,
  } = merged;
  window.localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      defaultModelId,
      defaultReasoningEffort,
      advancedReasoningBudgets,
      showRawToolCalls,
    }),
  );
}

const persisted = loadPersistedSettings();

export const useSettingsStore = create<SettingsState>()((set) => ({
  defaultModelId: (persisted.defaultModelId as string) ?? null,
  defaultReasoningEffort:
    (persisted.defaultReasoningEffort as ReasoningEffort) ?? "medium",
  advancedReasoningBudgets:
    (persisted.advancedReasoningBudgets as Record<string, number>) ?? {},
  showRawToolCalls: (persisted.showRawToolCalls as boolean) ?? false,
  modelCatalog: [],
  catalogDefaults: null,

  setDefaultModelId: (id) => {
    set({ defaultModelId: id });
    persist({ defaultModelId: id });
  },
  setDefaultReasoningEffort: (effort) => {
    set({ defaultReasoningEffort: effort });
    persist({ defaultReasoningEffort: effort });
  },
  setAdvancedReasoningBudget: (provider, budget) =>
    set((s) => {
      const next = { ...s.advancedReasoningBudgets, [provider]: budget };
      persist({ advancedReasoningBudgets: next });
      return { advancedReasoningBudgets: next };
    }),
  setShowRawToolCalls: (show) => {
    set({ showRawToolCalls: show });
    persist({ showRawToolCalls: show });
  },
  setModelCatalog: (models, defaults) =>
    set({ modelCatalog: models, catalogDefaults: defaults }),
  resetToDefaults: () => {
    const defaults = {
      defaultModelId: null,
      defaultReasoningEffort: "medium" as ReasoningEffort,
      advancedReasoningBudgets: {},
      showRawToolCalls: false,
    };
    set(defaults);
    persist(defaults);
  },
}));
