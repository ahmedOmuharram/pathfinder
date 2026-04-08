import { describe, it, expect, beforeEach } from "vitest";
import { useSettingsStore } from "./useSettingsStore";

beforeEach(() => {
  useSettingsStore.getState().resetToDefaults();
});

describe("state/useSettingsStore", () => {
  it("has correct defaults", () => {
    const s = useSettingsStore.getState();
    expect(s.showRawToolCalls).toBe(false);
    expect(s.showTokenUsage).toBe(true);
    expect(s.deleteFromWdk).toBe(false);
  });

  it("setShowRawToolCalls updates state", () => {
    useSettingsStore.getState().setShowRawToolCalls(true);
    expect(useSettingsStore.getState().showRawToolCalls).toBe(true);
  });

  it("setShowTokenUsage updates state", () => {
    useSettingsStore.getState().setShowTokenUsage(false);
    expect(useSettingsStore.getState().showTokenUsage).toBe(false);
  });

  it("setDeleteFromWdk updates state", () => {
    useSettingsStore.getState().setDeleteFromWdk(true);
    expect(useSettingsStore.getState().deleteFromWdk).toBe(true);
  });

  it("resetToDefaults restores all fields", () => {
    const store = useSettingsStore;
    store.getState().setShowRawToolCalls(true);
    store.getState().setShowTokenUsage(false);
    store.getState().setDeleteFromWdk(true);
    store.getState().resetToDefaults();
    const s = store.getState();
    expect(s.showRawToolCalls).toBe(false);
    expect(s.showTokenUsage).toBe(true);
    expect(s.deleteFromWdk).toBe(false);
  });
});
