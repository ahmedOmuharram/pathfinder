import { describe, expect, it, vi, afterEach } from "vitest";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

function makeLocalStorage(initial: Record<string, string> = {}) {
  const store = new Map<string, string>(Object.entries(initial));
  return {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
    raw: store,
  };
}

const STORAGE_KEY = "pathfinder-settings";

// ---------------------------------------------------------------------------
// Default initial state
// ---------------------------------------------------------------------------

describe("state/useSettingsStore - defaults", () => {
  it("initializes with default values when no localStorage", async () => {
    const mod = await import("./useSettingsStore");
    const state = mod.useSettingsStore.getState();

    expect(state.defaultModelId).toBeNull();
    expect(state.defaultReasoningEffort).toBe("medium");
    expect(state.modelOverrides).toEqual({});
    expect(state.showRawToolCalls).toBe(false);
    expect(state.showTokenUsage).toBe(true);
    expect(state.disabledTools).toEqual([]);
    expect(state.modelCatalog).toEqual([]);
    expect(state.catalogDefault).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// setDefaultModelId
// ---------------------------------------------------------------------------

describe("setDefaultModelId", () => {
  it("updates defaultModelId in state", async () => {
    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    store.getState().setDefaultModelId("openai/gpt-5");
    expect(store.getState().defaultModelId).toBe("openai/gpt-5");
  });

  it("sets defaultModelId to null", async () => {
    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    store.getState().setDefaultModelId("some-model");
    store.getState().setDefaultModelId(null);
    expect(store.getState().defaultModelId).toBeNull();
  });

  it("persists to localStorage", async () => {
    const localStorage = makeLocalStorage();
    vi.stubGlobal("window", { localStorage });

    const mod = await import("./useSettingsStore");
    mod.useSettingsStore.getState().setDefaultModelId("anthropic/claude-4");

    const persisted = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(persisted.defaultModelId).toBe("anthropic/claude-4");
  });
});

// ---------------------------------------------------------------------------
// setDefaultReasoningEffort
// ---------------------------------------------------------------------------

describe("setDefaultReasoningEffort", () => {
  it("updates reasoning effort", async () => {
    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    store.getState().setDefaultReasoningEffort("high");
    expect(store.getState().defaultReasoningEffort).toBe("high");
  });

  it("supports all reasoning effort levels", async () => {
    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    for (const effort of ["none", "low", "medium", "high"] as const) {
      store.getState().setDefaultReasoningEffort(effort);
      expect(store.getState().defaultReasoningEffort).toBe(effort);
    }
  });

  it("persists to localStorage", async () => {
    const localStorage = makeLocalStorage();
    vi.stubGlobal("window", { localStorage });

    const mod = await import("./useSettingsStore");
    mod.useSettingsStore.getState().setDefaultReasoningEffort("low");

    const persisted = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(persisted.defaultReasoningEffort).toBe("low");
  });
});

// ---------------------------------------------------------------------------
// setModelOverride
// ---------------------------------------------------------------------------

describe("setModelOverride", () => {
  it("adds an override for a model", async () => {
    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    store.getState().setModelOverride("openai/gpt-5", "contextSize", 100_000);
    expect(store.getState().modelOverrides["openai/gpt-5"]).toEqual({
      contextSize: 100_000,
    });
  });

  it("updates an existing override field", async () => {
    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    store.getState().setModelOverride("openai/gpt-5", "contextSize", 100_000);
    store.getState().setModelOverride("openai/gpt-5", "contextSize", 200_000);
    expect(store.getState().modelOverrides["openai/gpt-5"]?.contextSize).toBe(200_000);
  });

  it("supports multiple fields per model", async () => {
    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    store
      .getState()
      .setModelOverride("anthropic/claude-sonnet-4-0", "contextSize", 100_000);
    store
      .getState()
      .setModelOverride("anthropic/claude-sonnet-4-0", "reasoningBudget", 16384);

    const overrides = store.getState().modelOverrides["anthropic/claude-sonnet-4-0"];
    expect(overrides).toEqual({ contextSize: 100_000, reasoningBudget: 16384 });
  });

  it("removes override when set to undefined", async () => {
    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    store.getState().setModelOverride("openai/gpt-5", "contextSize", 100_000);
    store.getState().setModelOverride("openai/gpt-5", "contextSize", undefined);
    expect(store.getState().modelOverrides["openai/gpt-5"]).toBeUndefined();
  });

  it("persists to localStorage", async () => {
    const localStorage = makeLocalStorage();
    vi.stubGlobal("window", { localStorage });

    const mod = await import("./useSettingsStore");
    mod.useSettingsStore
      .getState()
      .setModelOverride("openai/gpt-5", "contextSize", 50_000);

    const persisted = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(persisted.modelOverrides["openai/gpt-5"]).toEqual({ contextSize: 50_000 });
  });
});

// ---------------------------------------------------------------------------
// setShowRawToolCalls
// ---------------------------------------------------------------------------

describe("setShowRawToolCalls", () => {
  it("toggles show raw tool calls on", async () => {
    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    store.getState().setShowRawToolCalls(true);
    expect(store.getState().showRawToolCalls).toBe(true);
  });

  it("toggles show raw tool calls off", async () => {
    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    store.getState().setShowRawToolCalls(true);
    store.getState().setShowRawToolCalls(false);
    expect(store.getState().showRawToolCalls).toBe(false);
  });

  it("persists to localStorage", async () => {
    const localStorage = makeLocalStorage();
    vi.stubGlobal("window", { localStorage });

    const mod = await import("./useSettingsStore");
    mod.useSettingsStore.getState().setShowRawToolCalls(true);

    const persisted = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(persisted.showRawToolCalls).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// setShowTokenUsage
// ---------------------------------------------------------------------------

describe("setShowTokenUsage", () => {
  it("toggles show token usage on", async () => {
    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    store.getState().setShowTokenUsage(true);
    expect(store.getState().showTokenUsage).toBe(true);
  });

  it("toggles show token usage off", async () => {
    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    store.getState().setShowTokenUsage(true);
    store.getState().setShowTokenUsage(false);
    expect(store.getState().showTokenUsage).toBe(false);
  });

  it("persists to localStorage", async () => {
    const localStorage = makeLocalStorage();
    vi.stubGlobal("window", { localStorage });

    const mod = await import("./useSettingsStore");
    mod.useSettingsStore.getState().setShowTokenUsage(true);

    const persisted = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(persisted.showTokenUsage).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// disabledTools / toggleTool
// ---------------------------------------------------------------------------

describe("disabledTools", () => {
  it("sets disabled tools list", async () => {
    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    store.getState().setDisabledTools(["tool_a", "tool_b"]);
    expect(store.getState().disabledTools).toEqual(["tool_a", "tool_b"]);
  });

  it("toggleTool adds a tool to the disabled list", async () => {
    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    store.getState().toggleTool("tool_x");
    expect(store.getState().disabledTools).toEqual(["tool_x"]);
  });

  it("toggleTool removes an already-disabled tool", async () => {
    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    store.getState().setDisabledTools(["tool_x", "tool_y"]);
    store.getState().toggleTool("tool_x");
    expect(store.getState().disabledTools).toEqual(["tool_y"]);
  });

  it("persists to localStorage", async () => {
    const localStorage = makeLocalStorage();
    vi.stubGlobal("window", { localStorage });

    const mod = await import("./useSettingsStore");
    mod.useSettingsStore.getState().setDisabledTools(["tool_a"]);

    const persisted = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(persisted.disabledTools).toEqual(["tool_a"]);
  });

  it("toggleTool persists to localStorage", async () => {
    const localStorage = makeLocalStorage();
    vi.stubGlobal("window", { localStorage });

    const mod = await import("./useSettingsStore");
    mod.useSettingsStore.getState().toggleTool("tool_z");

    const persisted = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(persisted.disabledTools).toEqual(["tool_z"]);
  });
});

// ---------------------------------------------------------------------------
// setModelCatalog
// ---------------------------------------------------------------------------

describe("setModelCatalog", () => {
  it("sets model catalog and catalog default", async () => {
    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    const models = [
      {
        id: "openai/gpt-5",
        name: "GPT-5",
        provider: "openai" as const,
        model: "gpt-5",
        supportsReasoning: true,
        enabled: true,
        contextSize: 400_000,
        defaultReasoningBudget: 0,
        description: "OpenAI GPT-5",
        inputPrice: 2.5,
        cachedInputPrice: 1.25,
        outputPrice: 10,
      },
      {
        id: "anthropic/claude-4",
        name: "Claude 4",
        provider: "anthropic" as const,
        model: "claude-4",
        supportsReasoning: true,
        enabled: true,
        contextSize: 200_000,
        defaultReasoningBudget: 8192,
        description: "Anthropic Claude 4",
        inputPrice: 3,
        cachedInputPrice: 1.5,
        outputPrice: 15,
      },
    ];

    store.getState().setModelCatalog(models, "openai/gpt-5");

    expect(store.getState().modelCatalog).toEqual(models);
    expect(store.getState().catalogDefault).toBe("openai/gpt-5");
  });

  it("does not persist catalog to localStorage", async () => {
    const localStorage = makeLocalStorage();
    vi.stubGlobal("window", { localStorage });

    const mod = await import("./useSettingsStore");
    mod.useSettingsStore.getState().setModelCatalog(
      [
        {
          id: "openai/gpt-5",
          name: "GPT-5",
          provider: "openai" as const,
          model: "gpt-5",
          supportsReasoning: true,
          enabled: true,
          contextSize: 400_000,
          defaultReasoningBudget: 0,
          description: "OpenAI GPT-5",
          inputPrice: 2.5,
          cachedInputPrice: 1.25,
          outputPrice: 10,
        },
      ],
      "openai/gpt-5",
    );

    // The catalog should NOT appear in persisted data - only user-editable fields
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const persisted = JSON.parse(raw);
      expect(persisted.modelCatalog).toBeUndefined();
      expect(persisted.catalogDefault).toBeUndefined();
    }
  });
});

// ---------------------------------------------------------------------------
// resetToDefaults
// ---------------------------------------------------------------------------

describe("resetToDefaults", () => {
  it("resets all user-editable state to defaults", async () => {
    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    // Set everything to non-default values
    store.getState().setDefaultModelId("anthropic/claude-4");
    store.getState().setDefaultReasoningEffort("high");
    store.getState().setModelOverride("openai/gpt-5", "contextSize", 50_000);
    store.getState().setShowRawToolCalls(true);
    store.getState().setShowTokenUsage(true);
    store.getState().setDisabledTools(["tool_a"]);

    // Reset
    store.getState().resetToDefaults();

    const state = store.getState();
    expect(state.defaultModelId).toBeNull();
    expect(state.defaultReasoningEffort).toBe("medium");
    expect(state.modelOverrides).toEqual({});
    expect(state.showRawToolCalls).toBe(false);
    expect(state.showTokenUsage).toBe(true);
    expect(state.disabledTools).toEqual([]);
  });

  it("persists reset state to localStorage", async () => {
    const localStorage = makeLocalStorage();
    vi.stubGlobal("window", { localStorage });

    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    store.getState().setDefaultModelId("some-model");
    store.getState().setShowTokenUsage(true);
    store.getState().setDisabledTools(["t"]);
    store.getState().resetToDefaults();

    const persisted = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(persisted.defaultModelId).toBeNull();
    expect(persisted.defaultReasoningEffort).toBe("medium");
    expect(persisted.modelOverrides).toEqual({});
    expect(persisted.showRawToolCalls).toBe(false);
    expect(persisted.showTokenUsage).toBe(true);
    expect(persisted.disabledTools).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Persistence — restoring from localStorage
// ---------------------------------------------------------------------------

describe("persistence", () => {
  it("restores settings from localStorage on init", async () => {
    const stored = {
      defaultModelId: "anthropic/claude-4",
      defaultReasoningEffort: "high",
      modelOverrides: { "openai/gpt-5": { contextSize: 50_000 } },
      showRawToolCalls: true,
      showTokenUsage: true,
      disabledTools: ["tool_a"],
    };
    vi.stubGlobal("window", {
      localStorage: makeLocalStorage({
        [STORAGE_KEY]: JSON.stringify(stored),
      }),
    });

    const mod = await import("./useSettingsStore");
    const state = mod.useSettingsStore.getState();

    expect(state.defaultModelId).toBe("anthropic/claude-4");
    expect(state.defaultReasoningEffort).toBe("high");
    expect(state.modelOverrides).toEqual({ "openai/gpt-5": { contextSize: 50_000 } });
    expect(state.showRawToolCalls).toBe(true);
    expect(state.showTokenUsage).toBe(true);
    expect(state.disabledTools).toEqual(["tool_a"]);
  });

  it("handles corrupted localStorage gracefully", async () => {
    vi.stubGlobal("window", {
      localStorage: makeLocalStorage({
        [STORAGE_KEY]: "not valid json!!!",
      }),
    });

    const mod = await import("./useSettingsStore");
    const state = mod.useSettingsStore.getState();

    // Should fall back to defaults
    expect(state.defaultModelId).toBeNull();
    expect(state.defaultReasoningEffort).toBe("medium");
  });

  it("handles missing localStorage key gracefully", async () => {
    vi.stubGlobal("window", {
      localStorage: makeLocalStorage({}),
    });

    const mod = await import("./useSettingsStore");
    const state = mod.useSettingsStore.getState();

    expect(state.defaultModelId).toBeNull();
    expect(state.defaultReasoningEffort).toBe("medium");
  });

  it("merges persisted state with existing values on subsequent calls", async () => {
    const localStorage = makeLocalStorage({
      [STORAGE_KEY]: JSON.stringify({ defaultModelId: "model-1" }),
    });
    vi.stubGlobal("window", { localStorage });

    const mod = await import("./useSettingsStore");
    const store = mod.useSettingsStore;

    // Changing reasoning effort should merge with existing persisted defaultModelId
    store.getState().setDefaultReasoningEffort("high");

    const persisted = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(persisted.defaultModelId).toBe("model-1");
    expect(persisted.defaultReasoningEffort).toBe("high");
  });
});
