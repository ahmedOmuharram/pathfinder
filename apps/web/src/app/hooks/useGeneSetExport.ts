import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import type { Strategy } from "@pathfinder/shared";
import { createGeneSetFromStrategy } from "@/features/workbench/api/geneSets";
import type { GeneSet } from "@/features/workbench/store";

interface UseGeneSetExportArgs {
  selectedSite: string;
  addGeneSet: (geneSet: GeneSet) => void;
}

export function useGeneSetExport({ selectedSite, addGeneSet }: UseGeneSetExportArgs) {
  const router = useRouter();
  const [exportingGeneSet, setExportingGeneSet] = useState(false);

  const handleExportAsGeneSet = useCallback(
    async (s: Strategy) => {
      if (!s.wdkStrategyId) return;

      // If the strategy already has an associated gene set, just navigate.
      if (s.geneSetId) {
        router.push(`/workbench/${s.geneSetId}`);
        return;
      }

      // No gene set yet — create one.
      setExportingGeneSet(true);
      try {
        const rootStep = s.rootStepId
          ? s.steps.find((step) => step.id === s.rootStepId)
          : null;
        const geneSet = await createGeneSetFromStrategy({
          name: s.name || "Strategy results",
          siteId: s.siteId || selectedSite,
          wdkStrategyId: s.wdkStrategyId,
          wdkStepId: rootStep?.wdkStepId ?? undefined,
          searchName: rootStep?.searchName ?? undefined,
          recordType: s.recordType ?? rootStep?.recordType ?? undefined,
          parameters: rootStep?.parameters ?? undefined,
        });
        addGeneSet(geneSet);
        router.push(`/workbench/${geneSet.id}`);
      } catch (err) {
        console.error("Failed to open strategy in workbench:", err);
      } finally {
        setExportingGeneSet(false);
      }
    },
    [selectedSite, addGeneSet, router],
  );

  return { exportingGeneSet, handleExportAsGeneSet };
}
