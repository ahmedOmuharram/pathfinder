"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  Search,
  Loader2,
  Plus,
  ThumbsUp,
  ThumbsDown,
  ChevronDown,
  X,
} from "lucide-react";
import type { GeneSearchResult } from "@pathfinder/shared";
import { listOrganisms, searchGenes } from "@/lib/api/genes";
import { createGeneSet } from "@/features/workbench/api/geneSets";
import { useSessionStore } from "@/state/useSessionStore";
import { useWorkbenchStore } from "../store";
import { Button } from "@/lib/components/ui/Button";

const PAGE_SIZE = 30;

export function GeneSearchSidebar() {
  const selectedSite = useSessionStore((s) => s.selectedSite);
  const addGeneSet = useWorkbenchStore((s) => s.addGeneSet);
  const evaluateOpen = useWorkbenchStore((s) => s.expandedPanels.has("evaluate"));
  const appendPositiveControls = useWorkbenchStore((s) => s.appendPositiveControls);
  const appendNegativeControls = useWorkbenchStore((s) => s.appendNegativeControls);

  // Search state
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GeneSearchResult[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Organism filter — fetched once per site, always visible
  const [organisms, setOrganisms] = useState<string[]>([]);
  const [selectedOrganism, setSelectedOrganism] = useState<string | null>(null);
  const [organismOpen, setOrganismOpen] = useState(false);
  const [organismFilter, setOrganismFilter] = useState("");
  const organismInputRef = useRef<HTMLInputElement>(null);

  // Fetch all organisms on mount / site change
  useEffect(() => {
    let cancelled = false;
    listOrganisms(selectedSite)
      .then((orgs) => {
        if (!cancelled) setOrganisms(orgs);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [selectedSite]);

  // Selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Hover detail — portal with fixed positioning
  const [hoveredGene, setHoveredGene] = useState<GeneSearchResult | null>(null);
  const [hoverPos, setHoverPos] = useState({ top: 0, right: 0 });
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sidebarRef = useRef<HTMLElement>(null);

  // New gene set name input
  const [showNameInput, setShowNameInput] = useState(false);
  const [newSetName, setNewSetName] = useState("");
  const [creating, setCreating] = useState(false);

  // Close organism dropdown on outside click
  const organismDropdownRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!organismOpen) return;
    const handler = (e: MouseEvent) => {
      if (
        organismDropdownRef.current &&
        !organismDropdownRef.current.contains(e.target as Node)
      ) {
        setOrganismOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [organismOpen]);

  // Debounced search
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const currentQueryRef = useRef("");

  const doSearch = useCallback(
    async (q: string, organism: string | null, append = false) => {
      if (!q.trim()) {
        if (!append) {
          setResults([]);
          setTotalCount(0);
        }
        return;
      }

      const offset = append ? results.length : 0;
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      setError(null);

      try {
        currentQueryRef.current = q;
        const resp = await searchGenes(selectedSite, q, organism, PAGE_SIZE, offset);
        // Discard stale responses
        if (currentQueryRef.current !== q) return;

        if (append) {
          setResults((prev) => [...prev, ...resp.results]);
        } else {
          setResults(resp.results);
        }
        setTotalCount(resp.totalCount);
      } catch (err) {
        if (currentQueryRef.current === q) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [selectedSite, results.length],
  );

  // Trigger search on query change (debounced)
  useEffect(() => {
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    if (!query.trim()) {
      setResults([]);
      setTotalCount(0);
      return;
    }
    searchTimeoutRef.current = setTimeout(() => {
      setSelectedIds(new Set());
      void doSearch(query, selectedOrganism);
    }, 300);
    return () => {
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, selectedOrganism, selectedSite]);

  // Toggle selection
  const toggleSelect = useCallback((geneId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(geneId)) next.delete(geneId);
      else next.add(geneId);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    if (selectedIds.size === results.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(results.map((r) => r.geneId)));
    }
  }, [selectedIds.size, results]);

  // Hover handlers
  const handleMouseEnter = useCallback(
    (gene: GeneSearchResult, e: React.MouseEvent<HTMLDivElement>) => {
      if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
      const rect = e.currentTarget.getBoundingClientRect();
      const sidebarRect = sidebarRef.current?.getBoundingClientRect();
      hoverTimeoutRef.current = setTimeout(() => {
        setHoveredGene(gene);
        setHoverPos({
          top: rect.top,
          right: window.innerWidth - (sidebarRect?.left ?? rect.left) + 8,
        });
      }, 300);
    },
    [],
  );

  const handleMouseLeave = useCallback(() => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    setHoveredGene(null);
  }, []);

  // Actions
  const handleCreateGeneSet = useCallback(async () => {
    if (selectedIds.size === 0) return;
    const name = newSetName.trim() || `Search: ${query.trim()}`;
    setCreating(true);
    try {
      const gs = await createGeneSet({
        name,
        source: "paste",
        geneIds: [...selectedIds],
        siteId: selectedSite,
      });
      addGeneSet(gs);
      setSelectedIds(new Set());
      setShowNameInput(false);
      setNewSetName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setCreating(false);
    }
  }, [selectedIds, newSetName, query, selectedSite, addGeneSet]);

  const handleAddPositive = useCallback(() => {
    if (selectedIds.size === 0) return;
    appendPositiveControls([...selectedIds]);
    setSelectedIds(new Set());
  }, [selectedIds, appendPositiveControls]);

  const handleAddNegative = useCallback(() => {
    if (selectedIds.size === 0) return;
    appendNegativeControls([...selectedIds]);
    setSelectedIds(new Set());
  }, [selectedIds, appendNegativeControls]);

  const hasSelection = selectedIds.size > 0;
  const hasMore = results.length < totalCount;

  return (
    <aside ref={sidebarRef} className="relative flex h-full flex-col overflow-hidden">
      {/* Search input */}
      <div className="space-y-2 border-b border-border px-3 py-3">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search genes..."
            className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-3 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        {/* Organism filter — searchable dropdown */}
        {organisms.length > 0 ? (
          <div ref={organismDropdownRef} className="relative">
            {selectedOrganism ? (
              <div className="flex h-7 w-full items-center justify-between rounded-md border border-input bg-background px-2.5 text-xs text-foreground">
                <span className="truncate italic">{selectedOrganism}</span>
                <button
                  type="button"
                  onClick={() => setSelectedOrganism(null)}
                  className="ml-1 shrink-0 rounded p-0.5 hover:bg-accent"
                >
                  <X className="h-3 w-3 text-muted-foreground" />
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => {
                  setOrganismOpen(!organismOpen);
                  setOrganismFilter("");
                  setTimeout(() => organismInputRef.current?.focus(), 0);
                }}
                className="flex h-7 w-full items-center justify-between rounded-md border border-input bg-background px-2.5 text-xs text-foreground"
              >
                <span className="truncate text-muted-foreground">
                  Filter by organism...
                </span>
                <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
              </button>
            )}
            {organismOpen && (
              <div className="absolute left-0 right-0 top-full z-20 mt-1 rounded-md border border-border bg-popover shadow-md">
                <div className="border-b border-border p-1.5">
                  <input
                    ref={organismInputRef}
                    type="text"
                    value={organismFilter}
                    onChange={(e) => setOrganismFilter(e.target.value)}
                    placeholder="Search organisms..."
                    className="h-6 w-full rounded border-none bg-transparent px-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none"
                    onKeyDown={(e) => {
                      if (e.key === "Escape") setOrganismOpen(false);
                    }}
                  />
                </div>
                <div className="max-h-48 overflow-y-auto">
                  {organisms
                    .filter((org) =>
                      org.toLowerCase().includes(organismFilter.toLowerCase()),
                    )
                    .map((org) => (
                      <button
                        key={org}
                        type="button"
                        onClick={() => {
                          setSelectedOrganism(org);
                          setOrganismOpen(false);
                          setOrganismFilter("");
                        }}
                        className="flex w-full items-center gap-2 px-3 py-1.5 text-xs hover:bg-accent"
                      >
                        <span className="truncate italic">{org}</span>
                      </button>
                    ))}
                  {organisms.filter((org) =>
                    org.toLowerCase().includes(organismFilter.toLowerCase()),
                  ).length === 0 && (
                    <p className="px-3 py-2 text-[10px] text-muted-foreground">
                      No organisms match.
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex h-7 items-center rounded-md border border-input bg-background px-2.5 text-xs text-muted-foreground">
            <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
            Loading organisms...
          </div>
        )}

        {/* Result count */}
        {query.trim() && !loading && (
          <p className="text-[10px] text-muted-foreground">
            {totalCount.toLocaleString()} result{totalCount !== 1 ? "s" : ""}
            {hasSelection && (
              <span className="ml-1 font-medium text-primary">
                ({selectedIds.size} selected)
              </span>
            )}
          </p>
        )}
      </div>

      {/* Results list */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="px-3 py-6 text-center text-xs text-destructive">{error}</div>
        ) : results.length === 0 && query.trim() ? (
          <div className="px-3 py-8 text-center text-xs text-muted-foreground">
            No genes found.
          </div>
        ) : results.length > 0 ? (
          <>
            {/* Select all */}
            <div className="flex items-center gap-2 border-b border-border px-3 py-1.5">
              <input
                type="checkbox"
                checked={results.length > 0 && selectedIds.size === results.length}
                onChange={toggleSelectAll}
                className="h-3.5 w-3.5 rounded border-border"
              />
              <span className="text-[10px] text-muted-foreground">Select all</span>
            </div>

            {results.map((gene) => (
              <div
                key={gene.geneId}
                onMouseEnter={(e) => handleMouseEnter(gene, e)}
                onMouseLeave={handleMouseLeave}
                className="flex items-start gap-2 border-b border-border/50 px-3 py-1.5 transition-colors hover:bg-accent/50"
              >
                <input
                  type="checkbox"
                  checked={selectedIds.has(gene.geneId)}
                  onChange={() => toggleSelect(gene.geneId)}
                  className="mt-0.5 h-3.5 w-3.5 shrink-0 rounded border-border"
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-foreground">
                    {gene.displayName || gene.product || gene.geneId}
                  </p>
                  <p className="truncate text-[10px] text-muted-foreground">
                    {gene.geneId}
                  </p>
                  <p className="truncate text-[10px] italic text-muted-foreground/70">
                    {gene.organism}
                  </p>
                </div>
              </div>
            ))}

            {/* Load more */}
            {hasMore && (
              <div className="px-3 py-2">
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full text-xs"
                  onClick={() => void doSearch(query, selectedOrganism, true)}
                  disabled={loadingMore}
                >
                  {loadingMore ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    `Load more (${results.length} of ${totalCount})`
                  )}
                </Button>
              </div>
            )}
          </>
        ) : null}
      </div>

      {/* Action bar */}
      <div className="space-y-2 border-t border-border px-3 py-3">
        {showNameInput ? (
          <div className="flex items-center gap-1.5">
            <input
              type="text"
              value={newSetName}
              onChange={(e) => setNewSetName(e.target.value)}
              placeholder={`Search: ${query.trim()}`}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleCreateGeneSet();
                if (e.key === "Escape") setShowNameInput(false);
              }}
              autoFocus
              className="h-7 flex-1 rounded-md border border-input bg-background px-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <Button
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => void handleCreateGeneSet()}
              disabled={creating}
            >
              {creating ? <Loader2 className="h-3 w-3 animate-spin" /> : "Add"}
            </Button>
          </div>
        ) : (
          <Button
            variant="outline"
            size="sm"
            className="w-full text-xs"
            disabled={!hasSelection}
            onClick={() => setShowNameInput(true)}
          >
            <Plus className="h-3 w-3" />
            Create gene set ({selectedIds.size})
          </Button>
        )}

        <Button
          variant="outline"
          size="sm"
          className="w-full text-xs"
          disabled={!hasSelection || !evaluateOpen}
          onClick={handleAddPositive}
          title={!evaluateOpen ? "Open the Evaluate panel to use this" : undefined}
        >
          <ThumbsUp className="h-3 w-3" />
          Add to + controls ({selectedIds.size})
        </Button>

        <Button
          variant="outline"
          size="sm"
          className="w-full text-xs"
          disabled={!hasSelection || !evaluateOpen}
          onClick={handleAddNegative}
          title={!evaluateOpen ? "Open the Evaluate panel to use this" : undefined}
        >
          <ThumbsDown className="h-3 w-3" />
          Add to − controls ({selectedIds.size})
        </Button>
      </div>

      {/* Hover detail popover — rendered via portal to escape overflow-hidden */}
      {hoveredGene &&
        createPortal(
          <div
            className="pointer-events-auto fixed z-50 w-64 rounded-lg border border-border bg-popover p-3 shadow-lg"
            style={{ top: hoverPos.top, right: hoverPos.right }}
            onMouseEnter={() => {
              if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
            }}
            onMouseLeave={handleMouseLeave}
          >
            <p className="text-xs font-semibold text-foreground">
              {hoveredGene.displayName || hoveredGene.geneId}
            </p>
            <p className="text-[10px] text-muted-foreground">{hoveredGene.geneId}</p>
            <dl className="mt-2 space-y-1 text-[10px]">
              <div>
                <dt className="font-medium text-muted-foreground">Product</dt>
                <dd className="text-foreground">{hoveredGene.product || "—"}</dd>
              </div>
              <div>
                <dt className="font-medium text-muted-foreground">Organism</dt>
                <dd className="italic text-foreground">{hoveredGene.organism}</dd>
              </div>
              {hoveredGene.geneName && (
                <div>
                  <dt className="font-medium text-muted-foreground">Gene name</dt>
                  <dd className="text-foreground">{hoveredGene.geneName}</dd>
                </div>
              )}
              {hoveredGene.geneType && (
                <div>
                  <dt className="font-medium text-muted-foreground">Type</dt>
                  <dd className="text-foreground">{hoveredGene.geneType}</dd>
                </div>
              )}
              {hoveredGene.location && (
                <div>
                  <dt className="font-medium text-muted-foreground">Location</dt>
                  <dd className="text-foreground">{hoveredGene.location}</dd>
                </div>
              )}
            </dl>
          </div>,
          document.body,
        )}
    </aside>
  );
}
