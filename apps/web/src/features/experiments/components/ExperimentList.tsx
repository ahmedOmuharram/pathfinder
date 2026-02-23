import { useEffect, useState } from "react";
import type { ExperimentSummary } from "@pathfinder/shared";
import { useExperimentStore } from "../store";
import {
  Plus,
  Search,
  Trash2,
  FlaskConical,
  Clock,
  Copy,
  Layers,
  BarChart3,
} from "lucide-react";

function pct(v: number | null | undefined): string {
  if (v == null) return "--";
  return `${(v * 100).toFixed(1)}%`;
}

function statusColor(status: string): string {
  switch (status) {
    case "completed":
      return "text-emerald-600 bg-emerald-50";
    case "running":
      return "text-indigo-600 bg-indigo-50";
    case "error":
      return "text-red-600 bg-red-50";
    default:
      return "text-slate-500 bg-slate-50";
  }
}

interface ExperimentListProps {
  siteId: string;
}

export function ExperimentList({ siteId }: ExperimentListProps) {
  const {
    experiments,
    fetchExperiments,
    loadExperiment,
    deleteExperiment,
    cloneExperiment,
    setView,
  } = useExperimentStore();
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetchExperiments(siteId);
  }, [siteId, fetchExperiments]);

  const filtered = experiments.filter(
    (e) =>
      !search ||
      e.name.toLowerCase().includes(search.toLowerCase()) ||
      e.searchName.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 p-3">
        <button
          type="button"
          onClick={() => setView("setup")}
          className="flex w-full items-center justify-center gap-2 rounded-md bg-slate-900 px-3 py-2 text-[12px] font-medium text-white transition hover:bg-slate-800"
        >
          <Plus className="h-3.5 w-3.5" />
          New Experiment
        </button>
        {experiments.filter((e) => e.status === "completed").length >= 2 && (
          <div className="mt-1.5 flex gap-1.5">
            <button
              type="button"
              onClick={() => setView("overlap")}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-md border border-slate-200 px-2 py-1.5 text-[10px] font-medium text-slate-600 transition hover:bg-slate-50"
            >
              <Layers className="h-3 w-3" />
              Overlap
            </button>
            <button
              type="button"
              onClick={() => setView("enrichment-compare")}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-md border border-slate-200 px-2 py-1.5 text-[10px] font-medium text-slate-600 transition hover:bg-slate-50"
            >
              <BarChart3 className="h-3 w-3" />
              Enrichment
            </button>
          </div>
        )}
      </div>

      <div className="border-b border-slate-200 px-3 py-2">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search experiments..."
            className="w-full rounded-md border border-slate-200 bg-white py-1.5 pl-7 pr-3 text-[12px] text-slate-700 outline-none placeholder:text-slate-400 focus:border-slate-300"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <FlaskConical className="mx-auto h-8 w-8 text-slate-300" />
            <p className="mt-2 text-[12px] text-slate-500">
              {experiments.length === 0
                ? "No experiments yet. Create one to get started."
                : "No experiments match your search."}
            </p>
          </div>
        ) : (
          <div className="space-y-0.5 p-1.5">
            {filtered.map((exp) => (
              <ExperimentCard
                key={exp.id}
                experiment={exp}
                onSelect={() => loadExperiment(exp.id)}
                onDelete={() => deleteExperiment(exp.id)}
                onClone={() => cloneExperiment(exp.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ExperimentCard({
  experiment: exp,
  onSelect,
  onDelete,
  onClone,
}: {
  experiment: ExperimentSummary;
  onSelect: () => void;
  onDelete: () => void;
  onClone: () => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter") onSelect();
      }}
      className="group relative flex w-full flex-col gap-1 rounded-md px-3 py-2 text-left transition hover:bg-slate-50"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0 truncate text-[12px] font-medium text-slate-800">
          {exp.name}
        </span>
        <span
          className={`shrink-0 rounded px-1.5 py-0.5 text-[9px] font-medium uppercase ${statusColor(exp.status)}`}
        >
          {exp.status}
        </span>
      </div>
      <div className="min-w-0 truncate text-[10px] text-slate-500">
        {exp.searchName}
      </div>
      <div className="flex items-center gap-3 text-[10px] text-slate-400">
        {exp.f1Score != null && (
          <span>
            F1: <span className="font-medium text-slate-600">{pct(exp.f1Score)}</span>
          </span>
        )}
        {exp.sensitivity != null && (
          <span>
            Sens:{" "}
            <span className="font-medium text-slate-600">{pct(exp.sensitivity)}</span>
          </span>
        )}
        <span className="ml-auto flex shrink-0 items-center gap-1">
          <Clock className="h-3 w-3" />
          {new Date(exp.createdAt).toLocaleDateString()}
        </span>
      </div>
      <div className="absolute right-2 top-2 hidden gap-0.5 group-hover:flex">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onClone();
          }}
          className="rounded p-1 text-slate-400 transition hover:bg-indigo-50 hover:text-indigo-500"
          title="Clone experiment"
        >
          <Copy className="h-3 w-3" />
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="rounded p-1 text-slate-400 transition hover:bg-red-50 hover:text-red-500"
          title="Delete experiment"
        >
          <Trash2 className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}
