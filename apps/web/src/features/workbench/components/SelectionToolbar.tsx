"use client";

import { useCallback, useMemo, useState } from "react";
import {
  Trash2,
  Download,
  GitCompare,
  Layers,
  CheckSquare,
  Square,
} from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { deleteGeneSet } from "../api/geneSets";
import { exportAsTxt, exportAsCsv, exportMultipleAsCsv } from "../utils/export";
import { useWorkbenchStore } from "../store";
import type { GeneSet } from "../store";
import { DeleteConfirmDialog } from "./DeleteConfirmDialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/lib/components/ui/DropdownMenu";

interface SelectionToolbarProps {
  activeSet: GeneSet | null;
  selectedSets: GeneSet[];
  allSetsCount: number;
  onCompare: () => void;
  onOverlap: () => void;
}

export function SelectionToolbar({
  activeSet,
  selectedSets,
  allSetsCount,
  onCompare,
  onOverlap,
}: SelectionToolbarProps) {
  const removeGeneSets = useWorkbenchStore((s) => s.removeGeneSets);
  const selectAll = useWorkbenchStore((s) => s.selectAll);
  const deselectAll = useWorkbenchStore((s) => s.deselectAll);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const toDelete = useMemo(
    () => (selectedSets.length > 0 ? selectedSets : activeSet ? [activeSet] : []),
    [selectedSets, activeSet],
  );
  const hasExactlyTwo = selectedSets.length === 2;
  const hasTwoOrMore = selectedSets.length >= 2;

  const handleDeleteRequest = useCallback(() => {
    if (toDelete.length === 0) return;
    setShowDeleteConfirm(true);
  }, [toDelete.length]);

  const handleDeleteConfirm = useCallback(async () => {
    setShowDeleteConfirm(false);
    setDeleting(true);
    setDeleteError(null);
    try {
      await Promise.all(toDelete.map((gs) => deleteGeneSet(gs.id)));
      removeGeneSets(toDelete.map((gs) => gs.id));
    } catch (err) {
      console.error("Failed to delete gene set(s):", err);
      setDeleteError("Some gene sets could not be deleted. Please try again.");
    } finally {
      setDeleting(false);
    }
  }, [toDelete, removeGeneSets]);

  const exportTarget =
    selectedSets.length > 0 ? selectedSets : activeSet ? [activeSet] : [];

  return (
    <>
      <div className="border-t border-border px-3 py-2.5">
        {/* Selection summary */}
        {allSetsCount > 0 && (
          <div className="mb-2 flex items-center justify-between">
            <p className="text-[10px] text-muted-foreground">
              {selectedSets.length > 0
                ? `${selectedSets.length} selected`
                : "None selected"}
            </p>
            <button
              type="button"
              onClick={selectedSets.length === allSetsCount ? deselectAll : selectAll}
              className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors"
            >
              {selectedSets.length === allSetsCount ? (
                <>
                  <Square className="h-3 w-3" /> Deselect all
                </>
              ) : (
                <>
                  <CheckSquare className="h-3 w-3" /> Select all
                </>
              )}
            </button>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex flex-wrap gap-1.5">
          <Button
            variant="outline"
            size="sm"
            disabled={toDelete.length === 0 || deleting}
            loading={deleting}
            onClick={handleDeleteRequest}
            className="gap-1 text-xs"
          >
            <Trash2 className="h-3.5 w-3.5" />
            {toDelete.length > 1 ? `Delete (${toDelete.length})` : "Delete"}
          </Button>

          {hasExactlyTwo && (
            <Button
              variant="outline"
              size="sm"
              onClick={onCompare}
              className="gap-1 text-xs"
            >
              <GitCompare className="h-3.5 w-3.5" />
              Compare
            </Button>
          )}

          {hasTwoOrMore && (
            <Button
              variant="outline"
              size="sm"
              onClick={onOverlap}
              className="gap-1 text-xs"
            >
              <Layers className="h-3.5 w-3.5" />
              Overlap
            </Button>
          )}

          {exportTarget.length > 0 && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="gap-1 text-xs">
                  <Download className="h-3.5 w-3.5" />
                  Export
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" side="top">
                {exportTarget.length === 1 && (
                  <>
                    <DropdownMenuItem onClick={() => exportAsCsv(exportTarget[0])}>
                      Export as CSV
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => exportAsTxt(exportTarget[0])}>
                      Export as TXT
                    </DropdownMenuItem>
                  </>
                )}
                {exportTarget.length > 1 && (
                  <DropdownMenuItem onClick={() => exportMultipleAsCsv(exportTarget)}>
                    Export {exportTarget.length} sets as CSV
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>

        {deleteError && (
          <p className="mt-2 text-xs text-destructive" role="alert">
            {deleteError}
          </p>
        )}
      </div>

      <DeleteConfirmDialog
        open={showDeleteConfirm}
        count={toDelete.length}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setShowDeleteConfirm(false)}
      />
    </>
  );
}
