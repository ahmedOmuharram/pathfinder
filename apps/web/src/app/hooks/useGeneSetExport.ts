import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import type { Strategy } from "@pathfinder/shared";
import { createGeneSetFromStrategy } from "@/features/workbench/api/geneSets";
import type { GeneSet } from "@/features/workbench/store";

interface UseGeneSetExportArgs {
  addGeneSet: (geneSet: GeneSet) => void;
}

export function useGeneSetExport({ addGeneSet }: UseGeneSetExportArgs) {
  const router = useRouter();
  const [exportingGeneSet, setExportingGeneSet] = useState(false);

  const handleExportAsGeneSet = useCallback(
    async (s: Strategy) => {
      if (s.wdkStrategyId === undefined || s.wdkStrategyId === null) return;

      // If the strategy already has an associated gene set, just navigate.
      if (s.geneSetId !== undefined && s.geneSetId !== null) {
        router.push(`/workbench/${s.geneSetId}`);
        return;
      }

      // No gene set yet — create one.
      setExportingGeneSet(true);
      try {
        const rootStep =
          s.rootStepId !== null && s.rootStepId !== undefined
            ? s.steps.find((step) => step.id === s.rootStepId)
            : null;
        const args: Parameters<typeof createGeneSetFromStrategy>[0] = {
          name: s.name,
          siteId: s.siteId,
          wdkStrategyId: s.wdkStrategyId,
        };
        if (rootStep !== null && rootStep !== undefined) {
          if (rootStep.wdkStepId !== undefined && rootStep.wdkStepId !== null) {
            args.wdkStepId = rootStep.wdkStepId;
          }
          if (rootStep.searchName !== undefined && rootStep.searchName !== null) {
            args.searchName = rootStep.searchName;
          }
          if (rootStep.parameters !== undefined && rootStep.parameters !== null) {
            args.parameters = rootStep.parameters;
          }
        }
        const recordType = s.recordType ?? rootStep?.recordType;
        if (recordType !== undefined && recordType !== null) {
          args.recordType = recordType;
        }
        const geneSet = await createGeneSetFromStrategy(args);
        addGeneSet(geneSet);
        router.push(`/workbench/${geneSet.id}`);
      } catch (err) {
        console.error("Failed to open strategy in workbench:", err);
      } finally {
        setExportingGeneSet(false);
      }
    },
    [addGeneSet, router],
  );

  return { exportingGeneSet, handleExportAsGeneSet };
}
