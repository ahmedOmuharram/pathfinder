import type { Strategy } from "@pathfinder/shared";

export type DuplicateModalState = {
  item: Strategy;
  name: string;
  description: string;
  isLoading: boolean;
  isSubmitting: boolean;
  error: string | null;
};

export function initDuplicateModal(item: Strategy): DuplicateModalState {
  return {
    item,
    name: item.name,
    description: "",
    isLoading: true,
    isSubmitting: false,
    error: null,
  };
}

export function applyDuplicateLoadSuccess(
  prev: DuplicateModalState,
  strategy: Strategy,
): DuplicateModalState {
  return {
    ...prev,
    name: strategy.name,
    description: strategy.description ?? "",
    isLoading: false,
  };
}

export function applyDuplicateLoadFailure(
  prev: DuplicateModalState,
): DuplicateModalState {
  return {
    ...prev,
    isLoading: false,
    error: "Failed to load strategy for duplication.",
  };
}

export function validateDuplicateName(name: string): string | null {
  if (!name.trim()) return "Name is required.";
  return null;
}

export function startDuplicateSubmit(prev: DuplicateModalState): DuplicateModalState {
  return { ...prev, isSubmitting: true, error: null };
}

export function applyDuplicateSubmitFailure(
  prev: DuplicateModalState,
): DuplicateModalState {
  return { ...prev, isSubmitting: false, error: "Failed to duplicate strategy." };
}
