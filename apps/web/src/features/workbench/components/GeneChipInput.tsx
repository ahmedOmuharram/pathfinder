"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ResolvedGene } from "@pathfinder/shared";
import { resolveGeneIds } from "@/lib/api/genes";
import { GeneChip, type ChipStatus } from "./GeneChip";
import { GeneAutocomplete } from "./GeneAutocomplete";
import { GeneSetPicker } from "./GeneSetPicker";
import { CsvImportButton } from "./CsvImportButton";
import { Label } from "@/lib/components/ui/Label";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GeneChipInputProps {
  siteId: string;
  value: string[];
  onChange: (ids: string[]) => void;
  label: string;
  required?: boolean;
  /** Visual tint: "positive" = green left border, "negative" = amber left border */
  tint?: "positive" | "negative" | "neutral";
}

interface VerificationState {
  resolved: Map<string, ResolvedGene>;
  invalid: Set<string>;
  pending: Set<string>;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function GeneChipInput({
  siteId,
  value,
  onChange,
  label,
  required = false,
  tint = "neutral",
}: GeneChipInputProps) {
  const [verification, setVerification] = useState<VerificationState>({
    resolved: new Map(),
    invalid: new Set(),
    pending: new Set(),
  });
  const verifyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastVerifiedRef = useRef<Set<string>>(new Set());
  // Ref to read current verification state inside the effect without making it a dep
  // (including `verification` directly would cause an infinite loop since the effect updates it).
  const verificationRef = useRef(verification);
  verificationRef.current = verification;

  // Auto-verify new gene IDs
  useEffect(() => {
    if (value.length === 0 || !siteId) return;

    const currentVerification = verificationRef.current;

    // Find IDs that haven't been verified yet
    const unverified = value.filter(
      (id) =>
        !lastVerifiedRef.current.has(id) &&
        !currentVerification.resolved.has(id) &&
        !currentVerification.invalid.has(id),
    );

    if (unverified.length === 0) return;

    // Mark as pending
    setVerification((prev) => {
      const pending = new Set(prev.pending);
      for (const id of unverified) pending.add(id);
      return { ...prev, pending };
    });

    // Debounced verification
    if (verifyTimer.current) clearTimeout(verifyTimer.current);
    verifyTimer.current = setTimeout(() => {
      void (async () => {
        try {
          const latestVerification = verificationRef.current;
          const result = await resolveGeneIds(siteId, unverified);
          const resolvedMap = new Map(latestVerification.resolved);
          const invalidSet = new Set(latestVerification.invalid);
          const pendingSet = new Set<string>();

          for (const gene of result.resolved) {
            resolvedMap.set(gene.geneId, gene);
            lastVerifiedRef.current.add(gene.geneId);
          }
          for (const id of result.unresolved) {
            invalidSet.add(id);
            lastVerifiedRef.current.add(id);
          }

          setVerification({
            resolved: resolvedMap,
            invalid: invalidSet,
            pending: pendingSet,
          });
        } catch {
          // Clear pending on error — don't block the user
          setVerification((prev) => ({ ...prev, pending: new Set() }));
        }
      })();
    }, 500);

    return () => {
      if (verifyTimer.current) clearTimeout(verifyTimer.current);
    };
  }, [value, siteId]);

  const getChipStatus = useCallback(
    (geneId: string): ChipStatus => {
      if (verification.resolved.has(geneId)) return "verified";
      if (verification.invalid.has(geneId)) return "invalid";
      return "pending";
    },
    [verification],
  );

  const handleRemove = useCallback(
    (geneId: string) => {
      onChange(value.filter((id) => id !== geneId));
    },
    [value, onChange],
  );

  const handleAddGene = useCallback(
    (geneId: string) => {
      if (!value.includes(geneId)) {
        onChange([...value, geneId]);
      }
    },
    [value, onChange],
  );

  const handleAddMany = useCallback(
    (geneIds: string[]) => {
      const existing = new Set(value);
      const newIds = geneIds.filter((id) => !existing.has(id));
      if (newIds.length > 0) {
        onChange([...value, ...newIds]);
      }
    },
    [value, onChange],
  );

  const tintClass =
    tint === "positive"
      ? "border-l-2 border-l-green-500 bg-green-500/[0.02]"
      : tint === "negative"
        ? "border-l-2 border-l-amber-500 bg-amber-500/[0.02]"
        : "";

  const excludeIds = new Set(value);

  return (
    <div
      className={`rounded-lg border border-border p-3 space-y-2 transition-colors duration-200 ${tintClass}`}
    >
      {/* Label */}
      <div className="flex items-center justify-between">
        <Label className="text-xs text-muted-foreground" required={required}>
          {label}
        </Label>
        {value.length > 0 && (
          <span className="text-[10px] text-muted-foreground tabular-nums">
            {value.length} gene{value.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Chips */}
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {value.map((geneId) => (
            <GeneChip
              key={geneId}
              geneId={geneId}
              status={getChipStatus(geneId)}
              resolvedGene={verification.resolved.get(geneId) ?? null}
              onRemove={handleRemove}
            />
          ))}
        </div>
      )}

      {/* Autocomplete search */}
      <GeneAutocomplete
        siteId={siteId}
        onSelect={handleAddGene}
        excludeIds={excludeIds}
      />

      {/* Action buttons */}
      <div className="flex flex-wrap items-center gap-2">
        <GeneSetPicker onSelect={handleAddMany} />
        <CsvImportButton onImport={handleAddMany} />
      </div>
    </div>
  );
}
