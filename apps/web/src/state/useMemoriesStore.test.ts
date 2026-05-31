import { describe, it, expect, beforeEach } from "vitest";
import type { MemoryItem } from "@pathfinder/shared";
import { useMemoriesStore } from "./useMemoriesStore";

function makeItem(overrides: Partial<MemoryItem["value"]> = {}): MemoryItem {
  return {
    key: "k",
    value: {
      kind: "knowledge",
      name: "a",
      summary: "b",
      tags: [],
      content: {},
      autoRetrieve: true,
      createdAt: new Date().toISOString(),
      ...overrides,
    },
  };
}

describe("state/useMemoriesStore", () => {
  beforeEach(() => {
    useMemoriesStore.getState().reset();
  });

  it("starts with empty lists, not loading, no error", () => {
    const state = useMemoriesStore.getState();
    expect(state.geneSets).toEqual([]);
    expect(state.strategies).toEqual([]);
    expect(state.preferences).toEqual([]);
    expect(state.knowledge).toEqual([]);
    expect(state.loading).toBe(false);
    expect(state.error).toBe(null);
  });

  it("setGroups populates all four namespaces", () => {
    const item = makeItem();
    useMemoriesStore.getState().setGroups({
      geneSets: [item],
      strategies: [],
      preferences: [makeItem({ kind: "preference" })],
      knowledge: [item],
      pageSize: 50,
      offset: 0,
      hasMore: false,
    });
    const s = useMemoriesStore.getState();
    expect(s.geneSets.length).toBe(1);
    expect(s.strategies.length).toBe(0);
    expect(s.preferences.length).toBe(1);
    expect(s.knowledge.length).toBe(1);
  });

  it("setLoading flips loading flag", () => {
    useMemoriesStore.getState().setLoading(true);
    expect(useMemoriesStore.getState().loading).toBe(true);
    useMemoriesStore.getState().setLoading(false);
    expect(useMemoriesStore.getState().loading).toBe(false);
  });

  it("setError stores error message and allows clearing", () => {
    useMemoriesStore.getState().setError("oops");
    expect(useMemoriesStore.getState().error).toBe("oops");
    useMemoriesStore.getState().setError(null);
    expect(useMemoriesStore.getState().error).toBe(null);
  });

  it("reset returns state to initial", () => {
    useMemoriesStore.getState().setGroups({
      geneSets: [makeItem()],
      strategies: [],
      preferences: [],
      knowledge: [],
      pageSize: 50,
      offset: 0,
      hasMore: false,
    });
    useMemoriesStore.getState().setLoading(true);
    useMemoriesStore.getState().setError("x");
    useMemoriesStore.getState().reset();
    const s = useMemoriesStore.getState();
    expect(s.geneSets).toEqual([]);
    expect(s.loading).toBe(false);
    expect(s.error).toBe(null);
  });
});
