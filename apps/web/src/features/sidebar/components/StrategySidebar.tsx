"use client";

import { useEffect, useMemo, useState } from "react";
import {
  createStrategy,
  deleteStrategy,
  getStrategy,
  listStrategies,
  listSites,
  listWdkStrategies,
  openStrategy,
  pushStrategy,
  syncStrategyFromWdk,
} from "@/lib/api/client";
import { toUserMessage } from "@/lib/api/errors";
import { useSessionStore } from "@/state/useSessionStore";
import { SitePicker } from "@/features/sites/components/SitePicker";
import { useStrategyListStore } from "@/state/useStrategyListStore";
import { useStrategyStore } from "@/state/useStrategyStore";
import { serializeStrategyPlan } from "@/features/strategy/domain/graph";

interface StrategySidebarProps {
  siteId: string;
  onOpenStrategy?: (source: "new" | "open") => void;
  onToast?: (toast: {
    type: "success" | "error" | "warning" | "info";
    message: string;
  }) => void;
}

interface StrategyListItem {
  id: string;
  name: string;
  updatedAt: string;
  siteId?: string;
  wdkStrategyId?: number;
  source: "draft" | "synced";
  isRemote?: boolean;
  isTemporary?: boolean;
}

export function StrategySidebar({
  siteId,
  onOpenStrategy,
  onToast,
}: StrategySidebarProps) {
  const [mounted, setMounted] = useState(false);
  const [siteLabels, setSiteLabels] = useState<Record<string, string>>({});
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [syncingStrategyId, setSyncingStrategyId] = useState<string | null>(null);
  const strategyId = useSessionStore((state) => state.strategyId);
  const setStrategyId = useSessionStore((state) => state.setStrategyId);
  const setSelectedSite = useSessionStore((state) => state.setSelectedSite);
  const graphValidationStatus = useStrategyListStore(
    (state) => state.graphValidationStatus
  );
  const addStrategy = useStrategyListStore((state) => state.addStrategy);
  const removeStrategy = useStrategyListStore((state) => state.removeStrategy);
  const draftStrategy = useStrategyStore((state) => state.strategy);
  const canCreateNew =
    !draftStrategy || (draftStrategy.steps?.length ?? 0) > 0;
  const setStrategyMeta = useStrategyStore((state) => state.setStrategyMeta);
  const setStrategy = useStrategyStore((state) => state.setStrategy);
  const clearStrategy = useStrategyStore((state) => state.clear);
  const [strategyItems, setStrategyItems] = useState<StrategyListItem[]>([]);
  const [filter, setFilter] = useState<"all" | "draft" | "synced">("all");
  const [query, setQuery] = useState("");
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    item: StrategyListItem;
  } | null>(null);
  const [duplicateModal, setDuplicateModal] = useState<{
    item: StrategyListItem;
    name: string;
    description: string;
    isLoading: boolean;
    isSubmitting: boolean;
    error: string | null;
  } | null>(null);

  const reportError = (message: string) => {
    if (typeof onToast === "function") {
      onToast({ type: "error", message });
      return;
    }
    setDeleteError(message);
  };

  const reportSuccess = (message: string) => {
    if (typeof onToast === "function") {
      onToast({ type: "success", message });
    }
  };

  const applyOpenResult = async (
    response: Awaited<ReturnType<typeof openStrategy>>,
    source: "new" | "open"
  ) => {
    const nextId = response.strategyId;
    setStrategyId(nextId);
    addStrategy({
      id: nextId,
      name: "Draft Strategy",
      title: "Draft Strategy",
      siteId,
      recordType: null,
      stepCount: 0,
      resultCount: undefined,
      wdkStrategyId: undefined,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });
    clearStrategy();
    try {
      const full = await getStrategy(nextId);
      setStrategy(full);
      setStrategyMeta({
        name: full.name,
        recordType: full.recordType ?? undefined,
        siteId: full.siteId,
      });
      refreshStrategies();
      onOpenStrategy?.(source);
    } catch {
      clearStrategy();
    }
  };

  const refreshStrategies = () => {
    return Promise.allSettled([
      listStrategies(siteId),
      listWdkStrategies(siteId),
    ])
      .then(([localResult, remoteResult]) => {
        const local = localResult.status === "fulfilled" ? localResult.value : [];
        const remote =
          remoteResult.status === "fulfilled" ? remoteResult.value : [];
        const localItems: StrategyListItem[] = local.map((item) => ({
          id: item.id,
          name: item.name,
          updatedAt: item.updatedAt,
          siteId: item.siteId,
          wdkStrategyId: item.wdkStrategyId,
          source: item.wdkStrategyId ? "synced" : "draft",
          isRemote: false,
        }));
        const localByWdkId = new Map(
          localItems
            .filter((item) => item.wdkStrategyId)
            .map((item) => [item.wdkStrategyId, item])
        );
        const remoteItems: StrategyListItem[] = (remote || [])
          .filter((item) => item?.wdkStrategyId)
          .map((item) => ({
            id: `wdk:${item.wdkStrategyId}`,
            name: item.name,
            updatedAt: new Date().toISOString(),
            siteId: item.siteId,
            wdkStrategyId: item.wdkStrategyId,
            source: "synced" as const,
            isRemote: !localByWdkId.has(item.wdkStrategyId),
            isTemporary: Boolean(item.isTemporary),
          }))
          .filter((item) => item.isRemote);
        setStrategyItems([...localItems, ...remoteItems]);
      })
      .catch(() => {});
  };

  useEffect(() => {
    if (!contextMenu) return;
    const handleClick = () => setContextMenu(null);
    window.addEventListener("click", handleClick);
    return () => window.removeEventListener("click", handleClick);
  }, [contextMenu]);

  const loadStrategyForDuplicate = async (item: StrategyListItem) => {
    return await getStrategy(item.id);
  };

  const buildPlanFromStrategy = (
    strategy: Awaited<ReturnType<typeof getStrategy>>
  ) => {
    const stepsById = Object.fromEntries(
      strategy.steps.map((step) => [step.id, step])
    );
    const serialized = serializeStrategyPlan(stepsById, strategy);
    if (!serialized) {
      throw new Error("Failed to serialize strategy for duplication.");
    }
    return serialized.plan;
  };

  const handleDuplicate = async (
    item: StrategyListItem,
    name: string,
    description: string
  ) => {
    const baseStrategy = await loadStrategyForDuplicate(item);
    const plan = buildPlanFromStrategy({
      ...baseStrategy,
      name,
      description,
    });
    await createStrategy({
      name,
      siteId: baseStrategy.siteId,
      plan,
    });
    refreshStrategies();
  };

  const handleDeleteWorkflow = async (item: StrategyListItem) => {
    setStrategyItems((items) => items.filter((entry) => entry.id !== item.id));
    if (strategyId === item.id) {
      clearStrategy();
      if (strategyId) {
        removeStrategy(strategyId);
      }
      setStrategyId(null);
    }
    setDeleteError(null);
    await deleteStrategy(item.id).catch(() => {});
    refreshStrategies();
  };

  const handlePushOrLocalize = async (item: StrategyListItem) => {
    await pushStrategy(item.id);
    refreshStrategies();
  };

  const handleSyncFromWdk = async (item: StrategyListItem) => {
    if (!item.wdkStrategyId) {
      reportError("Strategy must be linked to WDK to sync.");
      return;
    }
    setSyncingStrategyId(item.id);
    try {
      const updated = await syncStrategyFromWdk(item.id);
      if (strategyId === item.id) {
        setStrategy(updated);
        setStrategyMeta({
          name: updated.name,
          recordType: updated.recordType ?? undefined,
          siteId: updated.siteId,
        });
      }
      reportSuccess(`Synced strategy from WDK (#${item.wdkStrategyId}).`);
      refreshStrategies();
    } catch (e) {
      reportError(toUserMessage(e, "Failed to sync strategy from WDK."));
    } finally {
      setSyncingStrategyId(null);
    }
  };

  useEffect(() => {
    let isActive = true;
    setMounted(true);
    refreshStrategies();
    listSites()
      .then((items) => {
        if (!isActive) return;
        const next: Record<string, string> = {};
        items.forEach((item) => {
          next[item.id] = item.displayName || item.name;
        });
        setSiteLabels(next);
      })
      .catch(() => {});
    return () => {
      isActive = false;
    };
  }, [siteId, draftStrategy?.id, draftStrategy?.updatedAt]);

  const filteredItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return strategyItems.filter((item) => {
      if (filter !== "all" && item.source !== filter) {
        return false;
      }
      if (!normalizedQuery) return true;
      return item.name.toLowerCase().includes(normalizedQuery);
    });
  }, [strategyItems, filter, query]);

  const activeId = strategyId || draftStrategy?.id || null;

  return (
    <div className="flex h-full flex-col gap-5 border-r border-slate-200 bg-white px-3 py-4">
      <div>
        <SitePicker
          value={siteId}
          onChange={setSelectedSite}
          showSelect
          showAuth={false}
          showVisit
          layout="stacked"
        />
      </div>
      <div>
        <div className="mb-3 flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          <span>Strategies</span>
          <button
            onClick={() => {
              if (!canCreateNew) return;
              openStrategy({ siteId })
                .then((response) => applyOpenResult(response, "new"))
                .catch(() => {});
            }}
            disabled={!canCreateNew}
            className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-600 hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-60"
          >
            New Strategy
          </button>
        </div>
        <div className="flex flex-col gap-2">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search strategies..."
            className="w-full rounded-md border border-slate-200 px-2 py-1 text-[11px] text-slate-700 placeholder:text-slate-400"
          />
          <div className="flex gap-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            {[
              { id: "all", label: "All" },
              { id: "synced", label: "Synced" },
              { id: "draft", label: "Draft" },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() =>
                  setFilter(item.id as "all" | "draft" | "synced")
                }
                className={`rounded-md border px-2 py-1 ${
                  filter === item.id
                    ? "border-slate-300 bg-slate-100 text-slate-700"
                    : "border-slate-200 bg-white text-slate-500"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div>
        {deleteError && (
          <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">
            {deleteError}
          </div>
        )}
        <div className="space-y-2">
          {filteredItems.length === 0 && (
            <div className="text-[11px] text-slate-500">No strategies yet.</div>
          )}
          {filteredItems.map((s) => (
            <div
              key={s.id}
              onContextMenu={(event) => {
                if (s.isRemote) {
                  return;
                }
                event.preventDefault();
                setContextMenu({ x: event.clientX, y: event.clientY, item: s });
              }}
              className={`group flex items-center justify-between rounded-md border px-3 py-2 text-[11px] ${
                activeId === s.id
                  ? "border-slate-300 bg-slate-100 text-slate-900"
                  : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50"
              }`}
            >
              <button
                onClick={() => {
                  const isRemote = s.isRemote && s.wdkStrategyId;
                  const payload = isRemote
                    ? { wdkStrategyId: s.wdkStrategyId, siteId }
                    : { strategyId: s.id };
                  openStrategy(payload)
                    .then((response) => applyOpenResult(response, "open"))
                    .catch(() => {});
                }}
                className="flex flex-1 flex-col text-left"
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-slate-800">
                    {s.name}
                  </span>
                  {graphValidationStatus[s.id] && (
                    <span
                      className="inline-flex h-2 w-2 rounded-full bg-red-500"
                      title="Validation issues"
                    />
                  )}
                </div>
                <span className="text-[10px] uppercase tracking-wide text-slate-400">
                  {s.isRemote
                    ? s.isTemporary
                      ? "WDK (open)"
                      : "WDK"
                    : s.source === "synced"
                      ? "Synced"
                      : "Draft"}
                </span>
                {s.siteId && (
                  <span className="text-[10px] uppercase tracking-wide text-slate-400">
                    {siteLabels[s.siteId] || s.siteId}
                  </span>
                )}
                <span className="text-[10px] text-slate-500">
                  {mounted
                    ? new Date(s.updatedAt).toLocaleString()
                    : s.updatedAt}
                </span>
              </button>
              {null}
            </div>
          ))}
        </div>
      </div>
      {contextMenu && (
        <div
          className="fixed z-50 min-w-[180px] rounded-md border border-slate-200 bg-white p-1 text-[12px] text-slate-700 shadow-lg"
          style={{ top: contextMenu.y, left: contextMenu.x }}
        >
          <button
            type="button"
            onClick={() => {
              const item = contextMenu.item;
              setContextMenu(null);
              setDuplicateModal({
                item,
                name: item.name,
                description: "",
                isLoading: true,
                isSubmitting: false,
                error: null,
              });
              loadStrategyForDuplicate(item)
                .then((strategy) => {
                  setDuplicateModal((prev) =>
                    prev
                      ? {
                          ...prev,
                          name: strategy.name || prev.name,
                          description: strategy.description || "",
                          isLoading: false,
                        }
                      : prev
                  );
                })
                .catch(() => {
                  setDuplicateModal((prev) =>
                    prev
                      ? {
                          ...prev,
                          isLoading: false,
                          error: "Failed to load strategy for duplication.",
                        }
                      : prev
                  );
                });
            }}
            className="w-full rounded px-2 py-1 text-left hover:bg-slate-50"
          >
            Duplicate
          </button>
          <button
            type="button"
            onClick={() => {
              const item = contextMenu.item;
              setContextMenu(null);
              handlePushOrLocalize(item).catch(() => {
                reportError("Failed to push strategy.");
              });
            }}
            className="w-full rounded px-2 py-1 text-left hover:bg-slate-50"
          >
            {`Push to ${
              siteLabels[contextMenu.item.siteId || siteId] ||
              contextMenu.item.siteId ||
              siteId ||
              "site"
            }`}
          </button>
          {contextMenu.item.wdkStrategyId && (
            <button
              type="button"
              onClick={() => {
                const item = contextMenu.item;
                setContextMenu(null);
                void handleSyncFromWdk(item);
              }}
              disabled={syncingStrategyId === contextMenu.item.id}
              className="w-full rounded px-2 py-1 text-left hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {syncingStrategyId === contextMenu.item.id
                ? "Syncing from WDK..."
                : "Sync from WDK"}
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              const item = contextMenu.item;
              setContextMenu(null);
              handleDeleteWorkflow(item).catch(() => {
                reportError("Failed to delete strategy. Please try again.");
              });
            }}
            className="w-full rounded px-2 py-1 text-left text-red-600 hover:bg-red-50"
          >
            Delete workflow
          </button>
        </div>
      )}
      {duplicateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-4 shadow-lg">
            <h3 className="text-sm font-semibold text-slate-800">
              Duplicate workflow
            </h3>
            <div className="mt-3 space-y-2">
              <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Name
              </label>
              <input
                value={duplicateModal.name}
                onChange={(event) =>
                  setDuplicateModal((prev) =>
                    prev ? { ...prev, name: event.target.value } : prev
                  )
                }
                disabled={duplicateModal.isLoading}
                className="w-full rounded-md border border-slate-200 px-3 py-2 text-[13px] text-slate-800"
              />
              <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Description
              </label>
              <textarea
                value={duplicateModal.description}
                onChange={(event) =>
                  setDuplicateModal((prev) =>
                    prev ? { ...prev, description: event.target.value } : prev
                  )
                }
                rows={3}
                disabled={duplicateModal.isLoading}
                className="w-full resize-none rounded-md border border-slate-200 px-3 py-2 text-[13px] text-slate-800"
              />
              {duplicateModal.isLoading && (
                <div className="text-[11px] text-slate-500">
                  Loading strategy details...
                </div>
              )}
              {duplicateModal.error && (
                <div className="text-[11px] text-red-600">
                  {duplicateModal.error}
                </div>
              )}
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDuplicateModal(null)}
                className="rounded-md px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500 hover:text-slate-700"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (duplicateModal.isLoading) return;
                  if (!duplicateModal.name.trim()) {
                    setDuplicateModal((prev) =>
                      prev ? { ...prev, error: "Name is required." } : prev
                    );
                    return;
                  }
                  setDuplicateModal((prev) =>
                    prev ? { ...prev, isSubmitting: true, error: null } : prev
                  );
                  try {
                    await handleDuplicate(
                      duplicateModal.item,
                      duplicateModal.name.trim(),
                      duplicateModal.description.trim()
                    );
                    setDuplicateModal(null);
                  } catch (error) {
                    setDuplicateModal((prev) =>
                      prev
                        ? {
                            ...prev,
                            isSubmitting: false,
                            error: "Failed to duplicate workflow.",
                          }
                        : prev
                    );
                  }
                }}
                disabled={duplicateModal.isSubmitting || duplicateModal.isLoading}
                className="rounded-md bg-slate-900 px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-white hover:bg-slate-700 disabled:opacity-60"
              >
                {duplicateModal.isSubmitting ? "Duplicating..." : "Duplicate"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
