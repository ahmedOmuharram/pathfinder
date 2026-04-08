"use client";

/**
 * Duplicate workflow for the conversation sidebar.
 *
 * Owns the duplicate-strategy modal state and handles
 * the full duplicate flow: load strategy, build plan, create copy.
 *
 * Uses useQueryClient() directly for cache invalidation after duplication.
 */

import { type Dispatch, type SetStateAction, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { createStrategy, getStrategy, strategiesListOptions, dismissedStrategiesOptions } from "@/lib/api/strategies";
import type { Strategy } from "@pathfinder/shared";
import { buildDuplicatePlan } from "@/features/sidebar/utils/duplicatePlan";
import {
  type DuplicateModalState,
  applyDuplicateLoadFailure,
  applyDuplicateLoadSuccess,
  initDuplicateModal,
} from "@/features/sidebar/utils/duplicateModalState";

interface UseDuplicateWorkflowArgs {
  siteId: string;
}

export interface DuplicateWorkflow {
  duplicateModal: DuplicateModalState | null;
  setDuplicateModal: Dispatch<SetStateAction<DuplicateModalState | null>>;
  handleDuplicate: (id: string, name: string, desc: string) => Promise<void>;
  startDuplicate: (strategy: Strategy) => void;
}

export function useDuplicateWorkflow({
  siteId,
}: UseDuplicateWorkflowArgs): DuplicateWorkflow {
  const queryClient = useQueryClient();
  const [duplicateModal, setDuplicateModal] = useState<DuplicateModalState | null>(
    null,
  );

  const handleDuplicate = async (strategyIdToDuplicate: string, name: string, description: string) => {
    const baseStrategy = await getStrategy(strategyIdToDuplicate);
    const plan = buildDuplicatePlan({ baseStrategy, name, description });
    await createStrategy({
      name,
      siteId: baseStrategy.siteId,
      plan,
    });
    void queryClient.invalidateQueries({ queryKey: strategiesListOptions(siteId).queryKey });
    void queryClient.invalidateQueries({ queryKey: dismissedStrategiesOptions(siteId).queryKey });
  };

  const startDuplicate = (strategy: Strategy) => {
    setDuplicateModal(initDuplicateModal(strategy));
    getStrategy(strategy.id)
      .then((loadedStrategy) => {
        setDuplicateModal((prev) =>
          prev ? applyDuplicateLoadSuccess(prev, loadedStrategy) : prev,
        );
      })
      .catch((err) => {
        console.error("[startDuplicate]", err);
        setDuplicateModal((prev) => (prev ? applyDuplicateLoadFailure(prev) : prev));
      });
  };

  return {
    duplicateModal,
    setDuplicateModal,
    handleDuplicate,
    startDuplicate,
  };
}
