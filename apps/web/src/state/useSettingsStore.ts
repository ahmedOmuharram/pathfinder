/**
 * User settings store — persisted to localStorage.
 *
 * Stores default model/provider/reasoning preferences and
 * per-model tuning overrides.
 */

import { create } from "zustand";
import type { ModelCatalogEntry, ReasoningEffort } from "@pathfinder/shared";

const STORAGE_KEY = "pathfinder-settings";

export interface ModelOverrides {
  contextSize?: number;
  responseTokens?: number;
  reasoningBudget?: number;
}

interface SettingsState {
  /** Default model catalog ID (e.g. "openai/gpt-5"). null = use server default. */
  defaultModelId: string | null;
  /** Default reasoning effort. */
  defaultReasoningEffort: ReasoningEffort;
  /** Per-model tuning overrides keyed by catalog ID (e.g. "openai/gpt-5"). */
  modelOverrides: Record<string, ModelOverrides>;
  /** Show raw tool calls in chat (advanced). */
  showRawToolCalls: boolean;
  /** Show token usage under messages (advanced). */
  showTokenUsage: boolean;
  /** Tool names the user has disabled. */
  disabledTools: string[];
  /** When true, sidebar delete removes from WDK too (not just dismiss). */
  deleteFromWdk: boolean;

  /** Cached model catalog from the API. */
  modelCatalog: ModelCatalogEntry[];
  /** Unified server default model catalog ID (e.g. "openai/gpt-5"). */
  catalogDefault: string | null;

  // Actions
  setDefaultModelId: (id: string | null) => void;
  setDefaultReasoningEffort: (effort: ReasoningEffort) => void;
  setModelOverride: (
    modelId: string,
    field: keyof ModelOverrides,
    value: number | undefined,
  ) => void;
  setShowRawToolCalls: (show: boolean) => void;
  setShowTokenUsage: (show: boolean) => void;
  setDisabledTools: (tools: string[]) => void;
  toggleTool: (name: string) => void;
  setDeleteFromWdk: (v: boolean) => void;
  setModelCatalog: (models: ModelCatalogEntry[], defaultModelId: string) => void;
  resetToDefaults: () => void;
}

function loadPersistedSettings(): Partial<SettingsState> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === null) return {};
    return JSON.parse(raw) as Partial<SettingsState>;
  } catch {
    return {};
  }
}

function persist(partial: Partial<SettingsState>) {
  if (typeof window === "undefined") return;
  const current = loadPersistedSettings();
  const merged = { ...current, ...partial };
  const {
    defaultModelId,
    defaultReasoningEffort,
    modelOverrides,
    showRawToolCalls,
    showTokenUsage,
    disabledTools,
    deleteFromWdk,
  } = merged;
  window.localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      defaultModelId,
      defaultReasoningEffort,
      modelOverrides,
      showRawToolCalls,
      showTokenUsage,
      disabledTools,
      deleteFromWdk,
    }),
  );
}

const persisted = loadPersistedSettings();

export const useSettingsStore = create<SettingsState>()((set) => ({
  defaultModelId: persisted.defaultModelId ?? null,
  defaultReasoningEffort: persisted.defaultReasoningEffort ?? "medium",
  modelOverrides: persisted.modelOverrides ?? {},
  showRawToolCalls: persisted.showRawToolCalls ?? false,
  showTokenUsage: persisted.showTokenUsage ?? true,
  disabledTools: persisted.disabledTools ?? [],
  deleteFromWdk: persisted.deleteFromWdk ?? false,
  modelCatalog: [],
  catalogDefault: null,

  setDefaultModelId: (id) => {
    set({ defaultModelId: id });
    persist({ defaultModelId: id });
  },
  setDefaultReasoningEffort: (effort) => {
    set({ defaultReasoningEffort: effort });
    persist({ defaultReasoningEffort: effort });
  },
  setModelOverride: (modelId, field, value) =>
    set((s) => {
      const prev = s.modelOverrides[modelId] ?? {};
      const updated = { ...prev, [field]: value };
      // Remove undefined fields to keep storage clean.
      if (value === undefined) delete updated[field];
      const next = { ...s.modelOverrides };
      if (Object.keys(updated).length === 0) {
        delete next[modelId];
      } else {
        next[modelId] = updated;
      }
      persist({ modelOverrides: next });
      return { modelOverrides: next };
    }),
  setShowRawToolCalls: (show) => {
    set({ showRawToolCalls: show });
    persist({ showRawToolCalls: show });
  },
  setShowTokenUsage: (show) => {
    set({ showTokenUsage: show });
    persist({ showTokenUsage: show });
  },
  setDisabledTools: (tools) => {
    set({ disabledTools: tools });
    persist({ disabledTools: tools });
  },
  toggleTool: (name) =>
    set((s) => {
      const next = s.disabledTools.includes(name)
        ? s.disabledTools.filter((t) => t !== name)
        : [...s.disabledTools, name];
      persist({ disabledTools: next });
      return { disabledTools: next };
    }),
  setDeleteFromWdk: (v) => {
    set({ deleteFromWdk: v });
    persist({ deleteFromWdk: v });
  },
  setModelCatalog: (models, defaultModelId) =>
    set({ modelCatalog: models, catalogDefault: defaultModelId }),
  resetToDefaults: () => {
    const defaults = {
      defaultModelId: null,
      defaultReasoningEffort: "medium" as ReasoningEffort,
      modelOverrides: {},
      showRawToolCalls: false,
      showTokenUsage: true,
      disabledTools: [] as string[],
      deleteFromWdk: false,
    };
    set(defaults);
    persist(defaults);
  },
}));
