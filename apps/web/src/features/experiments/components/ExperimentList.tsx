import { useEffect, useState } from "react";
import type { ExperimentSummary } from "@pathfinder/shared";
import { useExperimentStore } from "../store";
import { Button } from "@/lib/components/ui/Button";
import { Input } from "@/lib/components/ui/Input";
import { Badge } from "@/lib/components/ui/Badge";
import { cn } from "@/lib/utils/cn";
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

function statusVariant(status: string) {
  switch (status) {
    case "completed":
      return "success" as const;
    case "running":
      return "default" as const;
    case "error":
      return "destructive" as const;
    default:
      return "secondary" as const;
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
      <div className="border-b border-border p-3">
        <Button className="w-full" onClick={() => setView("mode-select")}>
          <Plus className="h-4 w-4" />
          New Experiment
        </Button>
        {experiments.filter((e) => e.status === "completed").length >= 2 && (
          <div className="mt-1.5 flex gap-1.5">
            <Button
              variant="outline"
              size="sm"
              className="flex-1 text-xs"
              onClick={() => setView("overlap")}
            >
              <Layers className="h-3.5 w-3.5" />
              Overlap
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="flex-1 text-xs"
              onClick={() => setView("enrichment-compare")}
            >
              <BarChart3 className="h-3.5 w-3.5" />
              Enrichment
            </Button>
          </div>
        )}
      </div>

      <div className="border-b border-border px-3 py-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search experiments..."
            className="pl-8"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="px-4 py-8 text-center animate-fade-in">
            <FlaskConical className="mx-auto h-8 w-8 text-muted-foreground/40" />
            <p className="mt-2 text-sm text-muted-foreground">
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
      className="group relative flex w-full flex-col gap-1 rounded-lg px-3 py-2.5 text-left transition-all duration-150 hover:bg-accent"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0 truncate text-sm font-medium text-foreground">
          {exp.name}
        </span>
        <Badge variant={statusVariant(exp.status)} className="shrink-0 text-xs">
          {exp.status}
        </Badge>
      </div>
      <div className="min-w-0 truncate text-xs font-mono text-muted-foreground">
        {exp.searchName}
      </div>
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        {exp.f1Score != null && (
          <span>
            F1:{" "}
            <span className="font-mono font-medium text-foreground">
              {pct(exp.f1Score)}
            </span>
          </span>
        )}
        {exp.sensitivity != null && (
          <span>
            Sens:{" "}
            <span className="font-mono font-medium text-foreground">
              {pct(exp.sensitivity)}
            </span>
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
          className="rounded-md p-1 text-muted-foreground transition-colors duration-150 hover:bg-primary/10 hover:text-primary"
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
          className="rounded-md p-1 text-muted-foreground transition-colors duration-150 hover:bg-destructive/10 hover:text-destructive"
          title="Delete experiment"
        >
          <Trash2 className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}
