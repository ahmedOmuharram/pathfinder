"use client";

import { useEffect, useMemo, useState } from "react";
import type { Search } from "@pathfinder/shared";
import { getSearches } from "@/lib/api/client";

function looksLikeOrthologSearch(s: Search) {
  const hay =
    `${s.displayName || ""} ${s.description || ""} ${s.name || ""}`.toLowerCase();
  return (
    hay.includes("ortholog") || hay.includes("orthology") || hay.includes("orthomcl")
  );
}

export function OrthologTransformModal(props: {
  open: boolean;
  siteId: string;
  recordType: string;
  onCancel: () => void;
  onChoose: (search: Search, options: { insertBetween: boolean }) => void;
}) {
  const { open, siteId, recordType, onCancel, onChoose } = props;
  const [isLoading, setIsLoading] = useState(false);
  const [searches, setSearches] = useState<Search[]>([]);
  const [selectedName, setSelectedName] = useState<string>("");
  const [insertBetween, setInsertBetween] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    setIsLoading(true);
    setError(null);
    getSearches(siteId, recordType)
      .then((all) => {
        if (!alive) return;
        const matches = (all || []).filter(looksLikeOrthologSearch);
        setSearches(matches);
        setSelectedName(matches[0]?.name || "");
      })
      .catch((e) => {
        if (!alive) return;
        setError(e?.message || "Failed to load searches.");
        setSearches([]);
        setSelectedName("");
      })
      .finally(() => {
        if (!alive) return;
        setIsLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [open, siteId, recordType]);

  const selected = useMemo(
    () => searches.find((s) => s.name === selectedName) || null,
    [searches, selectedName],
  );

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white p-4 shadow-xl">
        <div className="text-sm font-semibold text-slate-900">
          Insert ortholog transform
        </div>
        <div className="mt-1 text-[12px] text-slate-500">
          Pick the site’s ortholog/orthology transform question. You can edit parameters
          after insertion.
        </div>

        <div className="mt-4 space-y-3">
          <div>
            <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Transform tool
            </label>
            {isLoading ? (
              <div className="text-[12px] text-slate-500">Loading…</div>
            ) : searches.length === 0 ? (
              <div className="text-[12px] text-slate-600">
                {error || "No ortholog transforms found for this record type."}
              </div>
            ) : (
              <select
                value={selectedName}
                onChange={(e) => setSelectedName(e.target.value)}
                className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
              >
                {searches.map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.displayName || s.name}
                  </option>
                ))}
              </select>
            )}
            {selected?.description ? (
              <div className="mt-2 text-[12px] text-slate-500">
                {selected.description}
              </div>
            ) : null}
          </div>

          <label className="flex items-center gap-2 text-[12px] text-slate-700">
            <input
              type="checkbox"
              checked={insertBetween}
              onChange={(e) => setInsertBetween(e.target.checked)}
            />
            Insert between selected step and its downstream step (when possible)
          </label>
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-400 hover:text-slate-600"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!selected}
            onClick={() => {
              if (!selected) return;
              onChoose(selected, { insertBetween });
            }}
            className="rounded-md border border-slate-200 bg-slate-900 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-white disabled:opacity-60"
          >
            Insert
          </button>
        </div>
      </div>
    </div>
  );
}
