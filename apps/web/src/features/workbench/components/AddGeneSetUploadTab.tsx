"use client";

import { useCallback, useRef, useState } from "react";
import { FileUp, Search } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { parseGeneIds } from "@/lib/utils/parseGeneIds";
import { useSessionStore } from "@/state/useSessionStore";
import { useWorkbenchStore } from "../store/useWorkbenchStore";
import type { ResolvedGene } from "@pathfinder/shared";
import { createGeneSet } from "../api/geneSets";
import { resolveGeneIds } from "@/lib/api/genes";
import { cn } from "@/lib/utils/cn";
import { VerificationResults } from "./VerificationResults";

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const ACCEPTED_FILE_TYPES = ".txt,.csv,.tsv";

const stripExtension = (filename: string): string => {
  const dotIndex = filename.lastIndexOf(".");
  return dotIndex > 0 ? filename.slice(0, dotIndex) : filename;
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

interface AddGeneSetUploadTabProps {
  onClose: () => void;
  onCreated: () => void;
}

export function AddGeneSetUploadTab({ onClose, onCreated }: AddGeneSetUploadTabProps) {
  const selectedSite = useSessionStore((s) => s.selectedSite);
  const addGeneSet = useWorkbenchStore((s) => s.addGeneSet);

  const [name, setName] = useState("");
  const [fileText, setFileText] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Verification state
  const [verifying, setVerifying] = useState(false);
  const [resolvedGenes, setResolvedGenes] = useState<ResolvedGene[] | null>(null);
  const [unresolvedIds, setUnresolvedIds] = useState<string[]>([]);
  const [verified, setVerified] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const parsedIds = parseGeneIds(fileText);
  const detectedCount = parsedIds.length;

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      setError(null);
      setVerified(false);
      setResolvedGenes(null);
      setUnresolvedIds([]);
      const reader = new FileReader();
      reader.onload = () => {
        const text = reader.result as string;
        setFileText(text);
        setFileName(file.name);
        if (!name) {
          setName(stripExtension(file.name));
        }
      };
      reader.onerror = () => {
        setError("Failed to read file. Please try again.");
      };
      reader.readAsText(file);
    },
    [name],
  );

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
        source: "upload",
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

      {/* File upload */}
      <div className="mt-4">
        <label
          htmlFor="gene-ids-upload"
          className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground"
        >
          Upload File
        </label>
        <div className="mt-1.5">
          <label
            htmlFor="gene-ids-upload"
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed border-border px-4 py-6 transition-colors hover:border-ring hover:bg-muted/50",
              isSubmitting && "pointer-events-none opacity-50",
            )}
          >
            <FileUp className="h-6 w-6 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">
              {fileName ?? "Choose a .txt, .csv, or .tsv file"}
            </span>
            <input
              ref={fileInputRef}
              id="gene-ids-upload"
              type="file"
              accept={ACCEPTED_FILE_TYPES}
              onChange={handleFileChange}
              disabled={isSubmitting}
              className="sr-only"
            />
          </label>
        </div>
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
