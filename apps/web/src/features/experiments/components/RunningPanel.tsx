import { useMemo, useRef, useEffect } from "react";
import {
  BarChart3,
  BrainCircuit,
  FlaskConical,
  Loader2,
  X,
  Sparkles,
  ArrowRight,
  GitBranch,
} from "lucide-react";
import { Card, CardContent } from "@/lib/components/ui/Card";
import { Button } from "@/lib/components/ui/Button";
import { Badge } from "@/lib/components/ui/Badge";
import { Progress } from "@/lib/components/ui/Progress";
import { useExperimentStore, type TrialHistoryEntry } from "../store";
import type { PlanStepNode } from "@pathfinder/shared";

const PHASE_LABELS: Record<string, string> = {
  started: "Initializing",
  optimizing: "Optimizing parameters",
  evaluating: "Evaluating",
  structural_analysis: "Analysing structure (AI)",
  cross_validating: "Cross-validating",
  enriching: "Computing enrichment",
  completed: "Complete",
  error: "Error",
};

// ---------------------------------------------------------------------------
// Mini strategy graph (SVG)
// ---------------------------------------------------------------------------

const NODE_W = 120;
const NODE_H = 32;
const COL_GAP = 44;
const ROW_GAP = 10;

const NODE_STYLES: Record<string, { fill: string; stroke: string; textFill: string }> =
  {
    search: { fill: "#ecfdf5", stroke: "#6ee7b7", textFill: "#065f46" },
    combine: { fill: "#eff6ff", stroke: "#93c5fd", textFill: "#1e40af" },
    transform: { fill: "#f5f3ff", stroke: "#c4b5fd", textFill: "#5b21b6" },
  };
const MUTATED_STROKE = "#f59e0b";

const OP_FILL: Record<string, string> = {
  INTERSECT: "#dbeafe",
  UNION: "#dcfce7",
  MINUS: "#ffedd5",
  RMINUS: "#fee2e2",
};
const OP_TEXT: Record<string, string> = {
  INTERSECT: "#1d4ed8",
  UNION: "#15803d",
  MINUS: "#c2410c",
  RMINUS: "#b91c1c",
};

type NodeKind = "search" | "combine" | "transform";

interface LayoutNode {
  node: PlanStepNode;
  kind: NodeKind;
  label: string;
  x: number;
  y: number;
  subtreeH: number;
  children: LayoutNode[];
}

function getNodeKind(node: PlanStepNode): NodeKind {
  if (node.primaryInput && node.secondaryInput) return "combine";
  if (node.primaryInput) return "transform";
  return "search";
}

function truncLabel(s: string, max: number): string {
  return s.length > max ? s.slice(0, max - 1) + "\u2026" : s;
}

function measureSubtree(node: PlanStepNode): { height: number; depth: number } {
  const kind = getNodeKind(node);
  if (kind === "search") return { height: NODE_H, depth: 0 };
  if (kind === "transform") {
    const child = measureSubtree(node.primaryInput!);
    return { height: Math.max(child.height, NODE_H), depth: child.depth + 1 };
  }
  const left = measureSubtree(node.primaryInput!);
  const right = measureSubtree(node.secondaryInput!);
  return {
    height: left.height + right.height + ROW_GAP,
    depth: Math.max(left.depth, right.depth) + 1,
  };
}

function layoutTree(node: PlanStepNode, x: number, yStart: number): LayoutNode {
  const kind = getNodeKind(node);
  const label = node.displayName || node.searchName;

  if (kind === "search") {
    return { node, kind, label, x, y: yStart, subtreeH: NODE_H, children: [] };
  }
  if (kind === "transform") {
    const child = layoutTree(node.primaryInput!, x - NODE_W - COL_GAP, yStart);
    const selfY = child.y + child.subtreeH / 2 - NODE_H / 2;
    return {
      node,
      kind,
      label,
      x,
      y: selfY,
      subtreeH: child.subtreeH,
      children: [child],
    };
  }
  const leftM = measureSubtree(node.primaryInput!);
  const leftChild = layoutTree(node.primaryInput!, x - NODE_W - COL_GAP, yStart);
  const rightChild = layoutTree(
    node.secondaryInput!,
    x - NODE_W - COL_GAP,
    yStart + leftM.height + ROW_GAP,
  );
  const totalH = leftM.height + measureSubtree(node.secondaryInput!).height + ROW_GAP;
  const selfY = yStart + totalH / 2 - NODE_H / 2;
  return {
    node,
    kind,
    label,
    x,
    y: selfY,
    subtreeH: totalH,
    children: [leftChild, rightChild],
  };
}

function flattenLayout(ln: LayoutNode): LayoutNode[] {
  const out: LayoutNode[] = [ln];
  for (const c of ln.children) out.push(...flattenLayout(c));
  return out;
}

interface MiniTreeProps {
  tree: PlanStepNode;
  mutatedNodeIds?: Set<string>;
}

function MiniTreeView({ tree, mutatedNodeIds }: MiniTreeProps) {
  const measure = measureSubtree(tree);
  const rootX = measure.depth * (NODE_W + COL_GAP);
  const PAD = 12;

  const root = layoutTree(tree, rootX, PAD);
  const allNodes = flattenLayout(root);

  const minX = Math.min(...allNodes.map((n) => n.x));
  const offsetX = -minX + PAD;
  for (const n of allNodes) n.x += offsetX;

  const svgW = rootX + offsetX + NODE_W + PAD;
  const svgH = measure.height + PAD * 2;

  const edges: { x1: number; y1: number; x2: number; y2: number }[] = [];
  function collectEdges(ln: LayoutNode) {
    for (const child of ln.children) {
      edges.push({
        x1: child.x + NODE_W,
        y1: child.y + NODE_H / 2,
        x2: ln.x,
        y2: ln.y + NODE_H / 2,
      });
      collectEdges(child);
    }
  }
  collectEdges(root);

  return (
    <div className="w-full overflow-auto rounded-lg border border-border bg-muted/20 p-2">
      <svg
        viewBox={`0 0 ${svgW} ${svgH}`}
        className="mx-auto block"
        style={{ width: svgW, height: svgH, maxWidth: "100%" }}
        preserveAspectRatio="xMidYMid meet"
      >
        {edges.map((e, i) => (
          <path
            key={i}
            d={`M${e.x1},${e.y1} C${e.x1 + 18},${e.y1} ${e.x2 - 18},${e.y2} ${e.x2},${e.y2}`}
            fill="none"
            stroke="hsl(var(--border))"
            strokeWidth={1.5}
          />
        ))}
        {allNodes.map((ln, i) => {
          const style = NODE_STYLES[ln.kind];
          const rx = ln.kind === "combine" ? 12 : ln.kind === "search" ? 10 : 5;
          const op = ln.kind === "combine" ? (ln.node.operator ?? "INTERSECT") : null;
          const isMutated = mutatedNodeIds?.has(ln.node.id ?? "");
          const stroke = isMutated ? MUTATED_STROKE : style.stroke;
          const sw = isMutated ? 2.5 : 1.5;

          return (
            <g key={i}>
              <rect
                x={ln.x}
                y={ln.y}
                width={NODE_W}
                height={NODE_H}
                rx={rx}
                fill={style.fill}
                stroke={stroke}
                strokeWidth={sw}
              />
              {isMutated && (
                <circle
                  cx={ln.x + NODE_W - 4}
                  cy={ln.y + 4}
                  r={3.5}
                  fill="#f59e0b"
                  stroke="#fff"
                  strokeWidth={1}
                />
              )}
              <text
                x={ln.x + NODE_W / 2}
                y={ln.y + (op ? 13 : NODE_H / 2 + 1)}
                textAnchor="middle"
                dominantBaseline="middle"
                fill={style.textFill}
                style={{ fontSize: 9, fontWeight: 600, fontFamily: "system-ui" }}
              >
                {truncLabel(ln.label, 16)}
              </text>
              {op && (
                <g>
                  <rect
                    x={ln.x + NODE_W / 2 - 20}
                    y={ln.y + NODE_H - 13}
                    width={40}
                    height={12}
                    rx={4}
                    fill={OP_FILL[op] ?? "#f1f5f9"}
                    stroke={OP_TEXT[op] ?? "#64748b"}
                    strokeWidth={0.8}
                  />
                  <text
                    x={ln.x + NODE_W / 2}
                    y={ln.y + NODE_H - 6.5}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill={OP_TEXT[op] ?? "#64748b"}
                    style={{ fontSize: 7.5, fontWeight: 700, fontFamily: "monospace" }}
                  >
                    {op}
                  </text>
                </g>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Score chart
// ---------------------------------------------------------------------------

function OptimizationChart({ trials }: { trials: TrialHistoryEntry[] }) {
  const W = 320;
  const H = 100;
  const PAD = { top: 10, right: 10, bottom: 18, left: 34 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  const maxScore = Math.max(...trials.map((t) => Math.max(t.score, t.bestScore)), 0.01);
  const minScore = Math.min(...trials.map((t) => Math.min(t.score, t.bestScore)), 0);
  const range = maxScore - minScore || 0.01;

  const x = (i: number) => PAD.left + (i / Math.max(trials.length - 1, 1)) * plotW;
  const y = (v: number) => PAD.top + plotH - ((v - minScore) / range) * plotH;

  const scoreLine = trials
    .map((t, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(t.score).toFixed(1)}`)
    .join(" ");
  const bestLine = trials
    .map(
      (t, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(t.bestScore).toFixed(1)}`,
    )
    .join(" ");

  const yTicks = [minScore, minScore + range / 2, maxScore];

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }}>
        {yTicks.map((v) => (
          <g key={v}>
            <line
              x1={PAD.left}
              y1={y(v)}
              x2={W - PAD.right}
              y2={y(v)}
              stroke="hsl(var(--border))"
              strokeWidth={0.5}
            />
            <text
              x={PAD.left - 4}
              y={y(v) + 3}
              textAnchor="end"
              fill="hsl(var(--muted-foreground))"
              style={{ fontSize: 7 }}
            >
              {v.toFixed(2)}
            </text>
          </g>
        ))}
        <path
          d={scoreLine}
          fill="none"
          stroke="hsl(var(--muted-foreground))"
          strokeWidth={1}
          opacity={0.5}
        />
        {trials.map((t, i) => (
          <circle
            key={`s${i}`}
            cx={x(i)}
            cy={y(t.score)}
            r={2}
            fill="hsl(var(--muted-foreground))"
          />
        ))}
        <path d={bestLine} fill="none" stroke="hsl(var(--primary))" strokeWidth={1.5} />
        {trials.length > 0 && (
          <circle
            cx={x(trials.length - 1)}
            cy={y(trials[trials.length - 1].bestScore)}
            r={3}
            fill="hsl(var(--primary))"
          />
        )}
        <text
          x={PAD.left + plotW / 2}
          y={H - 2}
          textAnchor="middle"
          fill="hsl(var(--muted-foreground))"
          style={{ fontSize: 7 }}
        >
          Trial
        </text>
      </svg>
      <div className="flex justify-center gap-3 text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="inline-block h-1 w-2.5 rounded-full bg-primary" /> Best
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-1 w-2.5 rounded-full bg-muted-foreground opacity-50" />{" "}
          Trial
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Trial mutations log
// ---------------------------------------------------------------------------

function TrialMutationRow({ entry }: { entry: TrialHistoryEntry }) {
  const params = entry.paramMutations ?? [];
  const ops = entry.operatorMutations ?? [];
  const sv = entry.structuralVariant;
  const hasMutations = params.length > 0 || ops.length > 0 || !!sv;

  return (
    <div
      className={`rounded-md border px-2 py-1.5 text-[11px] ${
        entry.isNewBest ? "border-primary/30 bg-primary/5" : "border-border bg-card"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="shrink-0 font-semibold text-foreground">
          #{entry.trialNumber}
        </span>
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-muted-foreground">
            {entry.score.toFixed(4)}
          </span>
          {entry.isNewBest && (
            <span className="rounded bg-primary/15 px-1 py-px text-[9px] font-bold text-primary">
              BEST
            </span>
          )}
        </div>
      </div>
      {hasMutations && (
        <div className="mt-1 space-y-0.5 border-t border-border/50 pt-1">
          {sv && (
            <div className="flex items-center gap-1 leading-tight text-muted-foreground">
              <span className="shrink-0 rounded bg-violet-100 px-1 py-px text-[9px] font-bold text-violet-700 dark:bg-violet-900/40 dark:text-violet-300">
                <GitBranch className="inline h-2 w-2" />
              </span>
              <span
                className="min-w-0 truncate text-[10px] font-medium text-violet-700 dark:text-violet-300"
                title={sv}
              >
                {sv}
              </span>
            </div>
          )}
          {params.map((m, i) => (
            <div
              key={`p${i}`}
              className="flex items-center gap-1 leading-tight text-muted-foreground"
            >
              <span className="shrink-0 rounded bg-amber-100 px-1 py-px text-[9px] font-bold text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
                P
              </span>
              <span
                className="min-w-0 truncate font-mono text-[10px]"
                title={`${m.nodeId} → ${m.param}`}
              >
                {m.param}
              </span>
              <ArrowRight className="h-2 w-2 shrink-0 text-muted-foreground/50" />
              <span className="shrink-0 font-mono text-[10px] font-medium text-foreground">
                {typeof m.value === "number" ? m.value.toFixed(2) : String(m.value)}
              </span>
            </div>
          ))}
          {ops.map((m, i) => (
            <div
              key={`o${i}`}
              className="flex items-center gap-1 leading-tight text-muted-foreground"
            >
              <span className="shrink-0 rounded bg-blue-100 px-1 py-px text-[9px] font-bold text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
                OP
              </span>
              <span className="min-w-0 truncate font-mono text-[10px]" title={m.nodeId}>
                {m.nodeId}
              </span>
              <ArrowRight className="h-2 w-2 shrink-0 text-muted-foreground/50" />
              <span className="shrink-0 font-mono text-[10px] font-medium text-foreground">
                {m.operator}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TrialLog({ trials }: { trials: TrialHistoryEntry[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [trials.length]);

  if (trials.length === 0) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center text-xs text-muted-foreground">
        Waiting for first trial...
      </div>
    );
  }

  return (
    <div ref={scrollRef} className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-0.5">
      {trials.map((t) => (
        <TrialMutationRow key={t.trialNumber} entry={t} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export function RunningPanel() {
  const { progress, trialHistory, hasOptimization, cancelExperiment, runningConfig } =
    useExperimentStore();

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const tp = (progress as any)?.trialProgress as
    | {
        totalTrials?: number;
        currentTrial?: number;
        bestScore?: number;
        phase?: string;
        message?: string;
        variantCount?: number;
        variantNames?: string[];
        bestTrial?: { score: number } | null;
        trial?: {
          trialNumber: number;
          score: number;
          recall?: number | null;
          resultCount?: number | null;
        } | null;
      }
    | undefined;

  const totalTrials = tp?.totalTrials ?? 0;
  const currentTrial = tp?.currentTrial ?? 0;
  const isTreeOpt = runningConfig?.enableTreeOptimization === true;
  const isStructuralAnalysis =
    progress?.phase === "optimizing" && tp?.phase === "structural_analysis";
  const isOptimizing = progress?.phase === "optimizing" && totalTrials > 0;
  const bestScore = tp?.bestScore ?? tp?.bestTrial?.score;

  const latestTrial =
    trialHistory.length > 0 ? trialHistory[trialHistory.length - 1] : null;

  const mutatedNodeIds = useMemo(() => {
    if (!latestTrial) return new Set<string>();
    const ids = new Set<string>();
    for (const m of latestTrial.paramMutations ?? []) {
      if (m.nodeId) ids.add(m.nodeId);
    }
    for (const m of latestTrial.operatorMutations ?? []) {
      if (m.nodeId) ids.add(m.nodeId);
    }
    return ids;
  }, [latestTrial]);

  // Tree optimization layout: full-width card with progress bar
  // on top, then graph + mutations side-by-side below.
  // Also show during structural analysis phase (before trials begin).
  if (isTreeOpt && (isOptimizing || isStructuralAnalysis)) {
    return (
      <div className="flex h-full flex-col p-6 animate-fade-in">
        <Card className="flex w-full flex-1 flex-col shadow-md">
          <CardContent className="flex flex-1 flex-col p-5">
            {/* Header row */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {isStructuralAnalysis ? (
                  <BrainCircuit className="h-6 w-6 animate-pulse text-violet-500" />
                ) : (
                  <FlaskConical className="h-6 w-6 animate-pulse text-primary" />
                )}
                <h2 className="text-base font-semibold text-foreground">
                  {isStructuralAnalysis
                    ? "Analysing Strategy Structure"
                    : "Optimizing Strategy Tree"}
                </h2>
                <Badge variant="secondary" className="text-xs">
                  {isStructuralAnalysis
                    ? (tp?.message ?? "AI is analysing...")
                    : (PHASE_LABELS[progress!.phase] ?? progress!.phase)}
                </Badge>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={cancelExperiment}
                className="hover:border-destructive hover:text-destructive"
              >
                <X className="h-3.5 w-3.5" />
                Cancel
              </Button>
            </div>

            {/* Progress bar */}
            <div className="mt-4">
              <Progress value={currentTrial} max={totalTrials} />
              <div className="mt-1 flex justify-between text-xs text-muted-foreground">
                <span>
                  Trial {currentTrial} / {totalTrials}
                </span>
                {bestScore != null && (
                  <span>
                    Best:{" "}
                    <span className="font-mono font-medium text-primary">
                      {bestScore.toFixed(4)}
                    </span>
                  </span>
                )}
              </div>
            </div>

            {/* Two columns: graph (left) + mutations (right) */}
            <div className="mt-4 grid min-h-0 flex-1 grid-cols-[1fr_300px] gap-4">
              {/* Left: tree + chart */}
              <div className="flex min-h-0 flex-col gap-3 overflow-hidden">
                {runningConfig?.stepTree && (
                  <div className="min-h-0 flex-1">
                    <MiniTreeView
                      tree={runningConfig.stepTree as PlanStepNode}
                      mutatedNodeIds={mutatedNodeIds}
                    />
                  </div>
                )}
                {trialHistory.length > 1 && (
                  <div className="shrink-0">
                    <OptimizationChart trials={trialHistory} />
                  </div>
                )}
              </div>

              {/* Right: mutations log */}
              <div className="flex min-h-0 flex-col rounded-lg border border-border bg-muted/20">
                <div className="flex shrink-0 items-center gap-1.5 border-b border-border px-3 py-2">
                  <Sparkles className="h-3.5 w-3.5 text-primary" />
                  <span className="text-xs font-semibold text-foreground">
                    Trial Mutations
                  </span>
                  <span className="ml-auto text-[10px] text-muted-foreground">
                    {trialHistory.length} done
                  </span>
                </div>
                <div className="flex min-h-0 flex-1 flex-col p-2">
                  <TrialLog trials={trialHistory} />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Standard layout (evaluation or single-step optimization)
  return (
    <div className="flex h-full items-center justify-center p-6 animate-fade-in">
      <Card className={`w-full shadow-md ${isOptimizing ? "max-w-3xl" : "max-w-2xl"}`}>
        <CardContent className="p-6">
          <div className="text-center">
            {hasOptimization ? (
              <FlaskConical className="mx-auto h-10 w-10 animate-pulse text-primary" />
            ) : (
              <BarChart3 className="mx-auto h-10 w-10 animate-pulse text-primary" />
            )}
            <h2 className="mt-3 text-lg font-semibold text-foreground">
              {hasOptimization ? "Running Experiment" : "Evaluating Strategy"}
            </h2>
            {progress && (
              <Badge variant="secondary" className="mt-2 text-xs">
                {PHASE_LABELS[progress.phase] ?? progress.phase}
              </Badge>
            )}
            {progress?.message && !isOptimizing && (
              <div className="mt-2 text-sm text-muted-foreground">
                {progress.message}
              </div>
            )}
          </div>

          {runningConfig?.stepTree && (
            <div className="mt-4">
              <MiniTreeView tree={runningConfig.stepTree as PlanStepNode} />
            </div>
          )}

          {isOptimizing && (
            <div className="mt-4 space-y-3">
              <div>
                <Progress value={currentTrial} max={totalTrials} />
                <div className="mt-1.5 flex justify-between text-xs text-muted-foreground">
                  <span>
                    Trial {currentTrial} / {totalTrials}
                  </span>
                  {bestScore != null && (
                    <span>
                      Best:{" "}
                      <span className="font-mono font-medium text-primary">
                        {bestScore.toFixed(4)}
                      </span>
                    </span>
                  )}
                </div>
              </div>
              {trialHistory.length > 1 && <OptimizationChart trials={trialHistory} />}
              {tp?.trial && (
                <div className="rounded-lg border border-border bg-muted/50 px-3 py-2 text-left text-xs text-muted-foreground">
                  <div className="mb-1 font-semibold text-foreground">
                    Latest trial #{tp.trial.trialNumber}
                  </div>
                  <div className="flex gap-4 font-mono">
                    <span>Score: {tp.trial.score.toFixed(4)}</span>
                    {tp.trial.recall != null && (
                      <span>Recall: {tp.trial.recall.toFixed(4)}</span>
                    )}
                    {tp.trial.resultCount != null && (
                      <span>Results: {tp.trial.resultCount}</span>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {progress && !isOptimizing && (
            <div className="mt-4 space-y-3">
              {progress.cvFoldIndex != null && progress.cvTotalFolds != null && (
                <div className="mx-auto w-48">
                  <Progress
                    value={progress.cvFoldIndex + 1}
                    max={progress.cvTotalFolds}
                  />
                </div>
              )}
              {progress.error && (
                <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-left text-sm text-destructive">
                  {progress.error}
                </div>
              )}
            </div>
          )}

          {!progress && (
            <div className="mt-4 flex items-center justify-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Connecting...
            </div>
          )}

          <div className="mt-5 text-center">
            <Button
              variant="outline"
              size="sm"
              onClick={cancelExperiment}
              className="hover:border-destructive hover:text-destructive"
            >
              <X className="h-3.5 w-3.5" />
              Cancel
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
