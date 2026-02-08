"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Trash2 } from "lucide-react";
import {
  APIError,
  deletePlanSession,
  getPlanSession,
  listPlans,
  openPlanSession,
} from "@/lib/api/client";
import { toUserMessage } from "@/lib/api/errors";
import { useSessionStore } from "@/state/useSessionStore";
import type { PlanSessionSummary } from "@pathfinder/shared";

export function PlansSidebar(props: {
  siteId: string;
  onToast?: (toast: {
    type: "success" | "error" | "warning" | "info";
    message: string;
  }) => void;
}) {
  const { siteId, onToast } = props;
  const planSessionId = useSessionStore((s) => s.planSessionId);
  const setPlanSessionId = useSessionStore((s) => s.setPlanSessionId);
  const setAuthToken = useSessionStore((s) => s.setAuthToken);
  const chatIsStreaming = useSessionStore((s) => s.chatIsStreaming);

  const [items, setItems] = useState<PlanSessionSummary[]>([]);
  const [query, setQuery] = useState("");

  const reportError = (message: string) => {
    onToast?.({ type: "error", message });
  };

  const handlePlanError = (error: unknown, fallback: string) => {
    if (error instanceof APIError && error.status === 401) {
      setAuthToken(null);
      setPlanSessionId(null);
      setItems([]);
      reportError("Session expired. Refresh to start a new plan.");
      return;
    }
    reportError(toUserMessage(error, fallback));
  };

  const refresh = useCallback(async () => {
    try {
      const sessions = await listPlans(siteId);
      setItems(sessions);
    } catch (error) {
      setItems([]);
      handlePlanError(error, "Failed to load plans.");
    }
  }, [handlePlanError, siteId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const visibleItems = useMemo(() => {
    // Backend hides empty plans. If the user just created a new empty plan,
    // show the active one optimistically so they can write into it immediately.
    if (!planSessionId) return items;
    const exists = items.some((p) => p.id === planSessionId);
    if (exists) return items;
    const now = new Date().toISOString();
    const optimistic: PlanSessionSummary = {
      id: planSessionId,
      siteId,
      title: "Plan",
      createdAt: now,
      updatedAt: now,
    };
    return [optimistic, ...items];
  }, [items, planSessionId, siteId]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return visibleItems;
    return visibleItems.filter((p) => p.title.toLowerCase().includes(q));
  }, [visibleItems, query]);

  const ensureActivePlan = useCallback(async () => {
    if (planSessionId) return;
    // On refresh, don't create a new plan session; reuse the most recent if it exists.
    const existing = await listPlans(siteId).catch((error) => {
      handlePlanError(error, "Failed to load plans.");
      return [];
    });
    if (existing.length > 0) {
      setItems(existing);
      setPlanSessionId(existing[0].id);
      return;
    }
    try {
      const res = await openPlanSession({ siteId, title: "Plan" });
      setPlanSessionId(res.planSessionId);
      await refresh();
    } catch (error) {
      handlePlanError(error, "Failed to open a new plan.");
    }
  }, [handlePlanError, planSessionId, refresh, setPlanSessionId, siteId]);

  useEffect(() => {
    void ensureActivePlan();
  }, [ensureActivePlan]);

  useEffect(() => {
    const handler = () => void refresh();
    window.addEventListener("plans:update", handler);
    return () => window.removeEventListener("plans:update", handler);
  }, [refresh]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 border-r border-slate-200 bg-white px-3 py-4">
      <div className="flex items-center justify-between">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Plans
        </div>
        <button
          type="button"
          disabled={chatIsStreaming}
          onClick={async () => {
            try {
              const res = await openPlanSession({ siteId, title: "Plan" });
              setPlanSessionId(res.planSessionId);
              // Optimistically show the new plan immediately even if it's empty.
              const now = new Date().toISOString();
              setItems((prev) => [
                {
                  id: res.planSessionId,
                  siteId,
                  title: "Plan",
                  createdAt: now,
                  updatedAt: now,
                },
                ...prev.filter((p) => p.id !== res.planSessionId),
              ]);
              // Refresh from server (will hide empty plans, but active plan stays visible via visibleItems).
              void refresh();
              // best-effort warm fetch
              void getPlanSession(res.planSessionId).catch((error) => {
                handlePlanError(error, "Failed to load the new plan.");
              });
            } catch (error) {
              handlePlanError(error, "Failed to open a new plan.");
            }
          }}
          className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-600 hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-60"
        >
          New Plan
        </button>
      </div>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search plans..."
        className="w-full rounded-md border border-slate-200 px-2 py-1 text-[11px] text-slate-700 placeholder:text-slate-400"
      />

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        <div className="space-y-2">
          {filtered.length === 0 && (
            <div className="text-[11px] text-slate-500">No plans yet.</div>
          )}
          {filtered.map((p) => {
            const isActive = planSessionId === p.id;
            return (
              <div
                key={p.id}
                className={`group flex w-full items-start justify-between gap-2 rounded-md border px-3 py-2 text-left text-[11px] ${
                  isActive
                    ? "border-slate-300 bg-slate-100 text-slate-900"
                    : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50"
                }`}
              >
                <button
                  type="button"
                  onClick={() => setPlanSessionId(p.id)}
                  className="min-w-0 flex-1 text-left"
                >
                  <div className="truncate text-sm font-medium text-slate-800">
                    {p.title}
                  </div>
                  <div className="text-[10px] text-slate-500">
                    {new Date(p.updatedAt).toLocaleString()}
                  </div>
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    const ok = window.confirm(
                      `Delete plan “${p.title}”? This cannot be undone.`,
                    );
                    if (!ok) return;
                    await deletePlanSession(p.id).catch((error) => {
                      handlePlanError(error, "Failed to delete plan.");
                    });
                    if (planSessionId === p.id) {
                      setPlanSessionId(null);
                    }
                    await refresh();
                    if (planSessionId === p.id) {
                      try {
                        const res = await openPlanSession({ siteId, title: "Plan" });
                        setPlanSessionId(res.planSessionId);
                        await refresh();
                      } catch (error) {
                        handlePlanError(error, "Failed to open a new plan.");
                      }
                    }
                  }}
                  className="rounded-md border border-slate-200 bg-white p-1.5 text-slate-500 opacity-0 transition hover:border-slate-300 hover:text-slate-900 group-hover:opacity-100"
                  aria-label="Delete plan"
                  title="Delete plan"
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
