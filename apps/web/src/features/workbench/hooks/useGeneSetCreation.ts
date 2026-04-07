"use client";

import { useCallback, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import type { ResolvedGene } from "@pathfinder/shared";
import { resolveGeneIds } from "@/lib/api/genes";
import { createGeneSet } from "../api/geneSets";
import { useSessionStore } from "@/state/useSessionStore";
import { useInvalidateGeneSets } from "@/lib/query/hooks/useInvalidateGeneSets";

interface UseGeneSetCreationOptions {
  onCreated: () => void;
}

export function useGeneSetCreation({ onCreated }: UseGeneSetCreationOptions) {
  const selectedSite = useSessionStore((s) => s.selectedSite);
  const invalidateGeneSets = useInvalidateGeneSets();

  const [error, setError] = useState<string | null>(null);

  const verifyMutation = useMutation({
    mutationFn: (parsedIds: string[]) => resolveGeneIds(selectedSite, parsedIds),
    onError: (err: Error) => {
      setError(err.message);
    },
    onMutate: () => {
      setError(null);
    },
  });

  const createMutation = useMutation({
    mutationFn: (args: { name: string; geneIds: string[]; source: "paste" | "upload" }) =>
      createGeneSet({
        name: args.name,
        source: args.source,
        geneIds: args.geneIds,
        siteId: selectedSite,
      }),
    onSuccess: async () => {
      await invalidateGeneSets();
      onCreated();
    },
    onError: (err: Error) => {
      setError(err.message);
    },
    onMutate: () => {
      setError(null);
    },
  });

  const verified = verifyMutation.isSuccess;
  const resolvedGenes: ResolvedGene[] | null = verifyMutation.data?.resolved ?? null;
  const unresolvedIds: string[] = verifyMutation.data?.unresolved ?? [];

  const resetVerification = useCallback(() => {
    verifyMutation.reset();
    setError(null);
  }, [verifyMutation]);

  const handleVerify = useCallback(
    (parsedIds: string[]) => {
      if (parsedIds.length === 0) return;
      verifyMutation.mutate(parsedIds);
    },
    [verifyMutation],
  );

  const handleSubmit = useCallback(
    (name: string, parsedIds: string[], source: "paste" | "upload") => {
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

      createMutation.mutate({ name: trimmedName, geneIds: idsToSubmit, source });
    },
    [verified, resolvedGenes, createMutation],
  );

  return {
    error,
    setError,
    isSubmitting: createMutation.isPending,
    verifying: verifyMutation.isPending,
    resolvedGenes,
    unresolvedIds,
    verified,
    resetVerification,
    handleVerify,
    handleSubmit,
  };
}
