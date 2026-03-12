"use client";

import { useCallback, useState } from "react";
import { Search } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { parseGeneIds } from "@/lib/utils/parseGeneIds";
import { useSessionStore } from "@/state/useSessionStore";
import { useWorkbenchStore } from "../store/useWorkbenchStore";
import type { ResolvedGene } from "@pathfinder/shared";
import { createGeneSet } from "../api/geneSets";
import { resolveGeneIds } from "@/lib/api/genes";
import { VerificationResults } from "./VerificationResults";

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

interface AddGeneSetPasteTabProps {
  onClose: () => void;
  onCreated: () => void;
}

export function AddGeneSetPasteTab({ onClose, onCreated }: AddGeneSetPasteTabProps) {
  const selectedSite = useSessionStore((s) => s.selectedSite);
  const addGeneSet = useWorkbenchStore((s) => s.addGeneSet);

  const [name, setName] = useState("");
  const [pasteText, setPasteText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Verification state
  const [verifying, setVerifying] = useState(false);
  const [resolvedGenes, setResolvedGenes] = useState<ResolvedGene[] | null>(null);
  const [unresolvedIds, setUnresolvedIds] = useState<string[]>([]);
  const [verified, setVerified] = useState(false);

  const parsedIds = parseGeneIds(pasteText);
  const detectedCount = parsedIds.length;

  const handlePasteChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setPasteText(e.target.value);
    setVerified(false);
    setResolvedGenes(null);
    setUnresolvedIds([]);
    setError(null);
  }, []);

  const handleVerify = useCallback(async () => {
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
  }, [parsedIds, selectedSite]);

  const handleSubmit = useCallback(async () => {
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
        source: "paste",
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
  }, [name, parsedIds, selectedSite, verified, resolvedGenes, addGeneSet, onCreated]);

  return (
    <>
      {/* Name input */}
      <div>
        <label
          htmlFor="gene-set-name"
          className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground"
        >
          Name
        </label>
        <input
          id="gene-set-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. My upregulated genes"
          disabled={isSubmitting}
          className="mt-1.5 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
        />
      </div>

      {/* Textarea */}
      <div className="mt-4">
        <label
          htmlFor="gene-ids-paste"
          className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground"
        >
          Gene IDs
        </label>
        <textarea
          id="gene-ids-paste"
          value={pasteText}
          onChange={handlePasteChange}
          placeholder="Paste gene IDs separated by newlines, commas, or tabs"
          rows={5}
          disabled={isSubmitting}
          className="mt-1.5 w-full resize-none rounded-md border border-border bg-background px-3 py-2 font-mono text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
        />
      </div>

      {/* Detection + verify row */}
      {detectedCount > 0 && (
        <div className="mt-3 flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            {detectedCount} gene{detectedCount !== 1 ? "s" : ""} detected
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleVerify}
            loading={verifying}
            disabled={verifying || isSubmitting}
            className="gap-1 text-xs"
          >
            <Search className="h-3 w-3" />
            Verify IDs
          </Button>
        </div>
      )}

      {/* Verification results */}
      {verified && resolvedGenes !== null && (
        <VerificationResults
          resolvedGenes={resolvedGenes}
          unresolvedIds={unresolvedIds}
        />
      )}

      {/* Error */}
      {error && (
        <p className="mt-3 text-xs text-destructive" role="alert">
          {error}
        </p>
      )}

      {/* Actions */}
      <div className="mt-5 flex justify-end gap-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onClose}
          disabled={isSubmitting}
        >
          Cancel
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={handleSubmit}
          loading={isSubmitting}
          disabled={detectedCount === 0}
        >
          {verified && resolvedGenes
            ? `Add ${resolvedGenes.length} Gene${resolvedGenes.length !== 1 ? "s" : ""}`
            : "Add Gene Set"}
        </Button>
      </div>
    </>
  );
}
