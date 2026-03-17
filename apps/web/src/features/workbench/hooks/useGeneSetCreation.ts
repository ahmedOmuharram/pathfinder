"use client";

import { useCallback, useState } from "react";
import type { ResolvedGene } from "@pathfinder/shared";
import { resolveGeneIds } from "@/lib/api/genes";
import { createGeneSet } from "../api/geneSets";
import { useSessionStore } from "@/state/useSessionStore";
import { useWorkbenchStore } from "../store/useWorkbenchStore";

interface UseGeneSetCreationOptions {
  onCreated: () => void;
}

export function useGeneSetCreation({ onCreated }: UseGeneSetCreationOptions) {
  const selectedSite = useSessionStore((s) => s.selectedSite);
  const addGeneSet = useWorkbenchStore((s) => s.addGeneSet);

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [resolvedGenes, setResolvedGenes] = useState<ResolvedGene[] | null>(null);
  const [unresolvedIds, setUnresolvedIds] = useState<string[]>([]);
  const [verified, setVerified] = useState(false);

  const resetVerification = useCallback(() => {
    setVerified(false);
    setResolvedGenes(null);
    setUnresolvedIds([]);
    setError(null);
  }, []);

  const handleVerify = useCallback(
    async (parsedIds: string[]) => {
      if (parsedIds.length === 0) return;
      setVerifying(true);
      setError(null);

      try {
        const result = await resolveGeneIds(selectedSite, parsedIds);
        setResolvedGenes(result.resolved);
        setUnresolvedIds(result.unresolved);
        setVerified(true);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to verify gene IDs.");
      } finally {
        setVerifying(false);
      }
    },
    [selectedSite],
  );

  const handleSubmit = useCallback(
    async (name: string, parsedIds: string[], source: "paste" | "upload") => {
      setError(null);

      const trimmedName = name.trim();
      if (!trimmedName) {
        setError("Please enter a name for the gene set.");
        return;
      }

      const idsToSubmit =
        verified && resolvedGenes ? resolvedGenes.map((g) => g.geneId) : parsedIds;

      if (idsToSubmit.length === 0) {
        setError("No valid gene IDs to add.");
        return;
      }

      setIsSubmitting(true);
      try {
        const geneSet = await createGeneSet({
          name: trimmedName,
          source,
          geneIds: idsToSubmit,
          siteId: selectedSite,
        });
        addGeneSet(geneSet);
        onCreated();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to create gene set.");
      } finally {
        setIsSubmitting(false);
      }
    },
    [selectedSite, verified, resolvedGenes, addGeneSet, onCreated],
  );

  return {
    error,
    setError,
    isSubmitting,
    verifying,
    resolvedGenes,
    unresolvedIds,
    verified,
    resetVerification,
    handleVerify,
    handleSubmit,
  };
}
