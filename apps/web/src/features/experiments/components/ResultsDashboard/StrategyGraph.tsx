import { useState, useEffect } from "react";
import {
  GitBranch,
  Search,
  Filter,
  ChevronRight,
  ChevronDown,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { Badge } from "@/lib/components/ui/Badge";
import { getExperimentStrategy } from "../../api";
import type { StrategyNode, StrategyResponse } from "../../api";

interface StrategyGraphProps {
  experimentId: string;
}

type StepType = "search" | "combine" | "transform";

function classifyStep(node: StrategyNode): StepType {
  if (node.primaryInput && node.secondaryInput) return "combine";
  if (node.primaryInput) return "transform";
  return "search";
}

const STEP_STYLES: Record<
  StepType,
  { icon: typeof Search; indicator: string; badgeCls: string; label: string }
> = {
  search: {
    icon: Search,
    indicator: "bg-blue-500",
    badgeCls: "bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/20",
    label: "Search",
  },
  combine: {
    icon: GitBranch,
    indicator: "bg-purple-500",
    badgeCls:
      "bg-purple-500/15 text-purple-700 dark:text-purple-400 border-purple-500/20",
    label: "Combine",
  },
  transform: {
    icon: Filter,
    indicator: "bg-emerald-500",
    badgeCls:
      "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/20",
    label: "Transform",
  },
};

function extractOperator(
  steps: StrategyResponse["steps"],
  stepId: number,
): string | null {
  const params = steps[String(stepId)]?.searchConfig?.parameters;
  if (!params) return null;
  const raw = params["bq_operator"] ?? params["operator"];
  if (!raw) return null;
  const labels: Record<string, string> = {
    INTERSECT: "Intersect",
    UNION: "Union",
    MINUS: "Minus",
    LONLY: "Left only",
    RONLY: "Right only",
  };
  return labels[raw] ?? raw;
}

function NodeCard({
  node,
  steps,
}: {
  node: StrategyNode;
  steps: StrategyResponse["steps"];
}) {
  const [expanded, setExpanded] = useState(false);
  const step = steps[String(node.stepId)];
  const stepType = classifyStep(node);
  const style = STEP_STYLES[stepType];
  const Icon = style.icon;
  const operator = stepType === "combine" ? extractOperator(steps, node.stepId) : null;
  const params = step?.searchConfig?.parameters;
  const hasParams = !!params && Object.keys(params).length > 0;

  return (
    <div className="shrink-0">
      <button
        type="button"
        onClick={() => hasParams && setExpanded((v) => !v)}
        className={`flex min-w-[180px] items-start gap-3 rounded-lg border border-border bg-card px-3.5 py-2.5 text-left shadow-sm transition ${
          hasParams
            ? "cursor-pointer hover:border-border/80 hover:shadow-md"
            : "cursor-default"
        }`}
      >
        <div className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${style.indicator}`} />

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <span className="truncate text-sm font-medium text-foreground">
              {step?.customName ?? step?.searchName ?? `Step ${node.stepId}`}
            </span>
          </div>

          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <Badge className={style.badgeCls}>{style.label}</Badge>
            {step?.estimatedSize != null && (
              <span className="font-mono text-xs tabular-nums text-muted-foreground">
                {step.estimatedSize.toLocaleString()} results
              </span>
            )}
          </div>

          {operator && (
            <div className="mt-1.5">
              <span className="rounded bg-purple-500/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide text-purple-600 dark:text-purple-400">
                {operator}
              </span>
            </div>
          )}

          {hasParams && (
            <div className="mt-1.5 flex items-center gap-1 text-[11px] text-muted-foreground">
              {expanded ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
              <span>{Object.keys(params).length} parameters</span>
            </div>
          )}
        </div>
      </button>

      {expanded && params && (
        <div className="ml-2 mt-1 rounded-md border border-border/50 bg-muted/50 px-3 py-2">
          <dl className="space-y-1">
            {Object.entries(params).map(([key, value]) => (
              <div key={key} className="flex gap-2 text-[11px]">
                <dt className="shrink-0 font-mono text-muted-foreground">{key}:</dt>
                <dd className="truncate text-foreground">{value || "—"}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}

function BranchConnector() {
  return (
    <div className="flex shrink-0 self-stretch">
      <div className="flex w-5 flex-col">
        <div className="flex-1 rounded-br-lg border-b-2 border-r-2 border-border/40" />
        <div className="flex-1 rounded-tr-lg border-t-2 border-r-2 border-border/40" />
      </div>
      <div className="flex items-center">
        <div className="w-3 border-t-2 border-border/40" />
      </div>
    </div>
  );
}

function StraightConnector() {
  return <div className="w-8 shrink-0 border-t-2 border-border/40" />;
}

function StepTree({
  node,
  steps,
}: {
  node: StrategyNode;
  steps: StrategyResponse["steps"];
}) {
  const hasInputs = !!node.primaryInput || !!node.secondaryInput;
  const hasBothInputs = !!node.primaryInput && !!node.secondaryInput;

  return (
    <div className="flex items-center">
      {hasInputs && (
        <div className="flex flex-col gap-3">
          {node.primaryInput && <StepTree node={node.primaryInput} steps={steps} />}
          {node.secondaryInput && <StepTree node={node.secondaryInput} steps={steps} />}
        </div>
      )}
      {hasBothInputs && <BranchConnector />}
      {hasInputs && !hasBothInputs && <StraightConnector />}
      <NodeCard node={node} steps={steps} />
    </div>
  );
}

export function StrategyGraph({ experimentId }: StrategyGraphProps) {
  const [strategy, setStrategy] = useState<StrategyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await getExperimentStrategy(experimentId);
        if (!cancelled) setStrategy(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load strategy");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [experimentId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">Loading strategy…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3">
        <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />
        <span className="text-sm text-destructive">{error}</span>
      </div>
    );
  }

  if (!strategy?.stepTree) {
    return (
      <div className="rounded-lg border border-border bg-muted/30 px-5 py-8 text-center text-sm text-muted-foreground">
        This experiment has no WDK strategy to display.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-baseline gap-2">
        <h3 className="text-sm font-medium text-foreground">{strategy.name}</h3>
        <span className="text-xs text-muted-foreground">
          Strategy #{strategy.strategyId}
        </span>
      </div>
      <div className="overflow-x-auto rounded-lg border border-border bg-card/50 p-6">
        <StepTree node={strategy.stepTree} steps={strategy.steps} />
      </div>
    </div>
  );
}
