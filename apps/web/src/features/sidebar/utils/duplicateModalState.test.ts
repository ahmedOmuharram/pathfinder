import { describe, expect, it } from "vitest";
import type { StrategyListItem } from "@/features/sidebar/utils/strategyItems";
import {
  applyDuplicateLoadFailure,
  applyDuplicateLoadSuccess,
  applyDuplicateSubmitFailure,
  initDuplicateModal,
  startDuplicateSubmit,
  validateDuplicateName,
} from "@/features/sidebar/utils/duplicateModalState";

describe("duplicateModalState", () => {
  it("initializes loading state from item", () => {
    const item = {
      id: "s1",
      name: "A",
      updatedAt: "t",
      source: "draft",
    } as StrategyListItem;
    const state = initDuplicateModal(item);
    expect(state.isLoading).toBe(true);
    expect(state.name).toBe("A");
  });

  it("applies load success and sets name/description", () => {
    const item = {
      id: "s1",
      name: "A",
      updatedAt: "t",
      source: "draft",
    } as StrategyListItem;
    const prev = initDuplicateModal(item);
    const next = applyDuplicateLoadSuccess(prev, {
      name: "New",
      description: "D",
    } as any);
    expect(next.isLoading).toBe(false);
    expect(next.name).toBe("New");
    expect(next.description).toBe("D");
  });

  it("applies load failure", () => {
    const item = {
      id: "s1",
      name: "A",
      updatedAt: "t",
      source: "draft",
    } as StrategyListItem;
    const prev = initDuplicateModal(item);
    const next = applyDuplicateLoadFailure(prev);
    expect(next.isLoading).toBe(false);
    expect(next.error).toMatch(/Failed to load/);
  });

  it("validates name required", () => {
    expect(validateDuplicateName("")).toBe("Name is required.");
    expect(validateDuplicateName(" ok ")).toBeNull();
  });

  it("submit state transitions", () => {
    const item = {
      id: "s1",
      name: "A",
      updatedAt: "t",
      source: "draft",
    } as StrategyListItem;
    const prev = initDuplicateModal(item);
    const started = startDuplicateSubmit({ ...prev, isLoading: false });
    expect(started.isSubmitting).toBe(true);
    const failed = applyDuplicateSubmitFailure(started);
    expect(failed.isSubmitting).toBe(false);
    expect(failed.error).toMatch(/Failed to duplicate/);
  });
});
