/**
 * Full Recharts-based optimization chart with tooltips, early-stop shading,
 * and responsive layout.
 *
 * This is intentionally separate from the SVG sparkline at
 * `features/experiments/components/RunningPanel/OptimizationChart.tsx` which
 * renders a compact, non-interactive sparkline in the running-panel sidebar.
 * The two share the same conceptual data (optimization trial scores) but use
 * fundamentally different rendering approaches (Recharts vs raw SVG) with
 * different size/interactivity trade-offs -- merging them would add more
 * complexity than it removes.
 */
import { useMemo } from "react";
import type { OptimizationTrial } from "@pathfinder/shared";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceArea,
  ReferenceLine,
} from "recharts";
import type { TooltipProps } from "recharts";
import { CHART_COLORS } from "@/lib/utils/chartTheme";

interface ScoreChartDatum {
  trial: number;
  score: number;
  bestSoFar: number;
}

const tooltipFormatter: NonNullable<TooltipProps["formatter"]> = (value, name) => [
  typeof value === "number" ? value.toFixed(4) : "--",
  name === "score" ? "Score" : "Best so far",
];

const CHART_HEIGHT = 320;

function buildTrialTicks(totalTrials: number): number[] {
  if (totalTrials <= 0) return [0];
  if (totalTrials <= 12) {
    return Array.from({ length: totalTrials + 1 }, (_, i) => i);
  }
  const step = Math.ceil(totalTrials / 10);
  const ticks: number[] = [];
  for (let t = 0; t <= totalTrials; t += step) ticks.push(t);
  if (ticks[ticks.length - 1] !== totalTrials) ticks.push(totalTrials);
  return ticks;
}

export function OptimizationChart({
  trials,
  totalTrials,
  currentTrial,
  isDone,
}: {
  trials: OptimizationTrial[];
  totalTrials: number;
  currentTrial: number;
  isDone: boolean;
}) {
  const chartData = useMemo<ScoreChartDatum[]>(() => {
    if (trials.length < 2) return [];

    let best = -Infinity;
    return trials.map((t) => {
      best = Math.max(best, t.score);
      return {
        trial: t.trialNumber,
        score: parseFloat(t.score.toFixed(4)),
        bestSoFar: parseFloat(best.toFixed(4)),
      };
    });
  }, [trials]);

  if (chartData.length < 2) return null;

  const effectiveTotal = Math.max(
    1,
    totalTrials,
    chartData[chartData.length - 1]?.trial ?? 1,
  );
  const stopTrial = Math.max(
    0,
    Math.min(
      effectiveTotal,
      Math.max(currentTrial, chartData[chartData.length - 1]?.trial ?? 0),
    ),
  );
  const hasEarlyStop = isDone && stopTrial < effectiveTotal;
  const trialTicks = buildTrialTicks(effectiveTotal);

  return (
    <div>
      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Score progression
      </div>
      <div className="rounded border border-border bg-muted px-1 py-1">
        <div
          style={{
            width: "100%",
            height: CHART_HEIGHT,
            contain: "size layout",
            overflow: "hidden",
          }}
        >
          <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
            <LineChart
              data={chartData}
              margin={{ top: 4, right: 8, bottom: 0, left: 8 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(var(--border))"
                vertical={false}
              />
              <XAxis
                type="number"
                dataKey="trial"
                domain={[0, effectiveTotal]}
                ticks={trialTicks}
                allowDataOverflow
                tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                type="number"
                domain={[0, 1]}
                ticks={[0, 0.25, 0.5, 0.75, 1]}
                tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }}
                tickLine={false}
                axisLine={false}
                width={32}
              />
              {hasEarlyStop ? (
                <>
                  <ReferenceArea
                    x1={stopTrial}
                    x2={effectiveTotal}
                    fill="hsl(var(--muted))"
                    fillOpacity={0.45}
                  />
                  <ReferenceLine
                    x={stopTrial}
                    stroke="hsl(var(--muted-foreground))"
                    strokeDasharray="4 4"
                    ifOverflow="visible"
                  />
                </>
              ) : null}
              <RechartsTooltip
                contentStyle={{
                  fontSize: 11,
                  padding: "4px 8px",
                  borderRadius: 6,
                  border: "1px solid hsl(var(--border))",
                }}
                labelFormatter={(v) => `Trial ${v}`}
                formatter={tooltipFormatter}
              />
              <Line
                type="monotone"
                dataKey="score"
                stroke="hsl(var(--muted-foreground))"
                strokeWidth={1}
                dot={false}
                isAnimationActive={false}
              />
              <Line
                type="stepAfter"
                dataKey="bestSoFar"
                stroke={CHART_COLORS.purple}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="mt-1 flex gap-3 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="inline-block h-px w-3 bg-muted-foreground" /> per-trial
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-px w-3 bg-primary" /> best so far
        </span>
      </div>
    </div>
  );
}
