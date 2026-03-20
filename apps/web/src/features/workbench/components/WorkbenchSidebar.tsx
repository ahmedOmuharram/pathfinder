"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronLeft, Plus } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { ScrollArea } from "@/lib/components/ui/ScrollArea";
import { TooltipProvider } from "@/lib/components/ui/Tooltip";
import { useWorkbenchStore } from "../store";
import { performSetOperation, createGeneSet } from "../api/geneSets";
import { useSessionStore } from "@/state/useSessionStore";
import { GeneSetCard } from "./GeneSetCard";
import { GeneSetFilter } from "./GeneSetFilter";
import { SetVenn } from "@/lib/components/SetVenn";
import { ComposeBar } from "./ComposeBar";
import { SelectionToolbar } from "./SelectionToolbar";
import { AddGeneSetModal } from "./AddGeneSetModal";
import { CompareModal } from "./CompareModal";
import { OverlapModal } from "./OverlapModal";

interface WorkbenchSidebarProps {
  onCollapse?: () => void;
}

export function WorkbenchSidebar({ onCollapse }: WorkbenchSidebarProps) {
  const router = useRouter();
  const geneSets = useWorkbenchStore((s) => s.geneSets);
  const activeSetId = useWorkbenchStore((s) => s.activeSetId);
  const selectedSetIds = useWorkbenchStore((s) => s.selectedSetIds);
  const setActiveSet = useWorkbenchStore((s) => s.setActiveSet);
  const toggleSetSelection = useWorkbenchStore((s) => s.toggleSetSelection);
  const addGeneSet = useWorkbenchStore((s) => s.addGeneSet);
  const clearSelection = useWorkbenchStore((s) => s.clearSelection);
  const selectedSite = useSessionStore((s) => s.selectedSite);

  const [filter, setFilter] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
  const [showCompare, setShowCompare] = useState(false);
  const [showOverlap, setShowOverlap] = useState(false);
  const [composing, setComposing] = useState(false);

  // Derived state
  const activeSet = geneSets.find((gs) => gs.id === activeSetId) ?? null;
  const selectedSets = geneSets.filter((gs) => selectedSetIds.includes(gs.id));
  const activeGeneIds = useMemo(() => activeSet?.geneIds ?? [], [activeSet]);

  const filteredSets = useMemo(() => {
    if (!filter.trim()) return geneSets;
    const q = filter.trim().toLowerCase();
    return geneSets.filter((gs) => gs.name.toLowerCase().includes(q));
  }, [geneSets, filter]);

  const showFilter = geneSets.length >= 5;
  const showVenn = selectedSets.length >= 2 && selectedSets.length <= 5;
  const showCompose = selectedSets.length === 2;

  // -- Handlers ---------------------------------------------------------------

  const handleVennRegionClick = useCallback(
    async (geneIds: string[], label: string) => {
      try {
        const gs = await createGeneSet({
          name: label,
          source: "derived",
          geneIds,
          siteId: selectedSite,
        });
        addGeneSet(gs);
        setActiveSet(gs.id);
        router.push(`/workbench/${gs.id}`);
      } catch (err) {
        console.error("Failed to create set from Venn region:", err);
      }
    },
    [selectedSite, addGeneSet, setActiveSet, router],
  );

  const handleComposeExecute = useCallback(
    async (result: { operation: string; geneIds: string[]; name: string }) => {
      const setA = selectedSets[0];
      const setB = selectedSets[1];
      if (selectedSets.length !== 2 || setA == null || setB == null) return;
      setComposing(true);
      try {
        const gs = await performSetOperation({
          operation: result.operation as "intersect" | "union" | "minus",
          setAId: setA.id,
          setBId: setB.id,
          name: result.name,
        });
        addGeneSet(gs);
        setActiveSet(gs.id);
        router.push(`/workbench/${gs.id}`);
        clearSelection();
      } catch (err) {
        console.error("Failed to execute set operation:", err);
      } finally {
        setComposing(false);
      }
    },
    [selectedSets, addGeneSet, setActiveSet, router, clearSelection],
  );

  return (
    <TooltipProvider delayDuration={300}>
      <aside className="flex h-full flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-3 pt-4 pb-2">
          <div className="flex items-center gap-1">
            {onCollapse && (
              <button
                type="button"
                onClick={onCollapse}
                aria-label="Collapse sidebar"
                className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </button>
            )}
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Gene Sets
            </h3>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowAddModal(true)}
            className="h-7 gap-1 px-2 text-xs"
          >
            <Plus className="h-3.5 w-3.5" />
            Add
          </Button>
        </div>

        {/* Filter (shown at 5+ sets) */}
        {showFilter && (
          <div className="px-3 pb-2">
            <GeneSetFilter value={filter} onChange={setFilter} />
          </div>
        )}

        {/* Zone 1: Library (scrollable list) */}
        <ScrollArea className="flex-1 px-3">
          {geneSets.length === 0 ? (
            <p className="px-1 py-4 text-xs text-muted-foreground">
              No gene sets yet. Click <strong>Add</strong> to get started.
            </p>
          ) : filteredSets.length === 0 ? (
            <p className="px-1 py-4 text-xs text-muted-foreground">
              No gene sets match &quot;{filter}&quot;
            </p>
          ) : (
            <div className="flex flex-col gap-0.5 pb-2">
              {filteredSets.map((gs) => (
                <GeneSetCard
                  key={gs.id}
                  geneSet={gs}
                  isActive={activeSetId === gs.id}
                  isSelected={selectedSetIds.includes(gs.id)}
                  activeGeneIds={activeGeneIds}
                  onActivate={() => {
                    setActiveSet(gs.id);
                    router.push(`/workbench/${gs.id}`);
                  }}
                  onToggleSelect={() => toggleSetSelection(gs.id)}
                />
              ))}
            </div>
          )}
        </ScrollArea>

        {/* Zone 2: Live Venn (when 2-5 selected) */}
        {showVenn && (
          <div className="border-t border-border px-3 py-3">
            <SetVenn
              sets={selectedSets.map((s) => ({
                key: s.name,
                geneIds: s.geneIds,
              }))}
              onRegionClick={(geneIds, label) => {
                void handleVennRegionClick(geneIds, label);
              }}
              height={selectedSets.length > 3 ? 280 : 200}
              width={240}
            />
          </div>
        )}

        {/* Zone 3: Compose (when 2 selected) */}
        {showCompose && selectedSets[0] != null && selectedSets[1] != null && (
          <div className="border-t border-border px-3 py-3">
            <ComposeBar
              setA={selectedSets[0]}
              setB={selectedSets[1]}
              onExecute={(result) => {
                void handleComposeExecute(result);
              }}
              loading={composing}
            />
          </div>
        )}

        {/* Bottom toolbar (always) */}
        <SelectionToolbar
          activeSet={activeSet}
          selectedSets={selectedSets}
          allSetsCount={geneSets.length}
          onCompare={() => setShowCompare(true)}
          onOverlap={() => setShowOverlap(true)}
        />

        {/* Modals */}
        <AddGeneSetModal open={showAddModal} onClose={() => setShowAddModal(false)} />

        {showCompare &&
          selectedSets.length === 2 &&
          selectedSets[0] != null &&
          selectedSets[1] != null && (
            <CompareModal
              open={showCompare}
              onClose={() => setShowCompare(false)}
              setA={selectedSets[0]}
              setB={selectedSets[1]}
            />
          )}

        {showOverlap && selectedSets.length >= 2 && (
          <OverlapModal
            open={showOverlap}
            onClose={() => setShowOverlap(false)}
            sets={selectedSets}
          />
        )}
      </aside>
    </TooltipProvider>
  );
}
