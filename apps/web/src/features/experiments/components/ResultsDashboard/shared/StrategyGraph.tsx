/**
 * Read-only strategy graph for the experiment results dashboard.
 *
 * This is intentionally separate from the full editable StrategyGraph at
 * `features/strategy/graph/components/StrategyGraph.tsx`. The editable version
 * has a large surface area: drag-and-drop, edge editing, combine/ortholog
 * modals, step editing, save/undo, selection modes, and hints -- all driven by
 * the `useStrategyGraph` hook. This read-only version is a self-contained
 * ~100-line component that fetches an experiment's strategy and renders it with
 * ReactFlow in non-interactive mode. Extracting a shared base would couple
 * this simple viewer to the editable graph's complex hook and modal wiring.
 */
import { useState, useEffect, useMemo } from "react";
import ReactFlow, { Background, Controls, MiniMap } from "reactflow";
import "reactflow/dist/style.css";
import { Loader2, AlertCircle } from "lucide-react";
import { StepNode } from "@/features/strategy/graph/components/StepNode";
import { deserializeStrategyToGraph } from "@/lib/strategyGraph";
import { getExperimentStrategy } from "../../../api";
import { strategyResponseToStrategy } from "../../../utils/strategyAdapter";

interface StrategyGraphProps {
  experimentId: string;
  siteId?: string;
  recordType?: string;
}

const NODE_TYPES = { step: StepNode } as const;
const FIT_VIEW_OPTIONS = { padding: 0.3 } as const;

export function StrategyGraph({
  experimentId,
  siteId = "",
  recordType,
}: StrategyGraphProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<ReturnType<
    typeof deserializeStrategyToGraph
  > | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const resp = await getExperimentStrategy(experimentId);
        if (cancelled) return;
        const strategy = strategyResponseToStrategy(resp, siteId, recordType);
        const graph = deserializeStrategyToGraph(strategy);
        if (!cancelled) setGraphData(graph);
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
  }, [experimentId, siteId, recordType]);

  const memoNodes = useMemo(() => graphData?.nodes ?? [], [graphData]);
  const memoEdges = useMemo(() => graphData?.edges ?? [], [graphData]);

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

  if (memoNodes.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-muted/30 px-5 py-8 text-center text-sm text-muted-foreground">
        This experiment has no WDK strategy to display.
      </div>
    );
  }

  return (
    <div className="h-[420px] overflow-hidden rounded-lg border border-border">
      <ReactFlow
        nodes={memoNodes}
        edges={memoEdges}
        nodeTypes={NODE_TYPES}
        fitView
        fitViewOptions={FIT_VIEW_OPTIONS}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag
        zoomOnScroll
        className="bg-background"
      >
        <Background gap={28} size={1} />
        <Controls showInteractive={false} />
        <MiniMap nodeStrokeWidth={3} zoomable pannable className="!bg-card" />
      </ReactFlow>
    </div>
  );
}
