import { useMemo } from "react";
import type { EnrichmentTerm } from "@pathfinder/shared";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  MAX_CHART_TERMS,
  DOT_MIN_R,
  DOT_MAX_R,
  pvalColor,
  truncateLabel,
} from "./enrichment-utils";

// ---------------------------------------------------------------------------
// Chart data type
// ---------------------------------------------------------------------------

interface DotChartDatum {
  name: string;
  foldEnrichment: number;
  geneCount: number;
  pValue: number;
  /** Pre-computed dot radius based on geneCount / maxGeneCount. */
  dotRadius: number;
}

// ---------------------------------------------------------------------------
// Custom bar shape (circle instead of rectangle)
// ---------------------------------------------------------------------------

function DotShape(props: {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  payload?: DotChartDatum;
}) {
  const { x = 0, y = 0, width = 0, height = 0, payload } = props;
  if (payload == null) return null;
  const d = payload;

  return (
    <circle
      cx={x + width}
      cy={y + height / 2}
      r={d.dotRadius}
      fill={pvalColor(d.pValue)}
      fillOpacity={0.85}
    />
  );
}

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

function DotPlotTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: DotChartDatum }>;
}) {
  if (active !== true || payload?.[0] == null) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded border border-border bg-card px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-medium text-foreground">{d.name}</p>
      <div className="flex gap-3 text-muted-foreground">
        <span>Fold: {d.foldEnrichment.toFixed(2)}</span>
        <span>Genes: {d.geneCount}</span>
        <span>p: {d.pValue.toExponential(2)}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Legend
// ---------------------------------------------------------------------------

function DotPlotLegend({ maxGeneCount }: { maxGeneCount: number }) {
  const sizes = [
    { count: Math.max(1, Math.round(maxGeneCount * 0.1)), r: DOT_MIN_R },
    {
      count: Math.max(2, Math.round(maxGeneCount * 0.5)),
      r: (DOT_MIN_R + DOT_MAX_R) / 2,
    },
    { count: maxGeneCount, r: DOT_MAX_R },
  ];
  return (
    <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
      <span className="flex items-center gap-1">
        <span
          className="inline-block h-2 w-8 rounded-sm"
          style={{
            background:
              "linear-gradient(to right, hsl(220,70%,55%), hsl(110,70%,50%), hsl(40,75%,50%), hsl(0,80%,50%))",
          }}
        />
        <span>-log10(p)</span>
      </span>
      <span className="flex items-center gap-1.5">
        {sizes.map((s) => (
          <span key={s.count} className="flex items-center gap-0.5">
            <svg width={s.r * 2 + 2} height={s.r * 2 + 2}>
              <circle
                cx={s.r + 1}
                cy={s.r + 1}
                r={s.r}
                fill="hsl(var(--muted-foreground))"
                fillOpacity={0.3}
                stroke="hsl(var(--muted-foreground))"
                strokeWidth={0.5}
              />
            </svg>
            <span>{s.count}</span>
          </span>
        ))}
        <span>genes</span>
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface EnrichmentDotPlotProps {
  terms: EnrichmentTerm[];
}

export function EnrichmentDotPlot({ terms }: EnrichmentDotPlotProps) {
  const { data, maxGeneCount } = useMemo(() => {
    const top = [...terms]
      .sort((a, b) => a.pValue - b.pValue)
      .slice(0, MAX_CHART_TERMS)
      .reverse();

    const maxGC = Math.max(...top.map((t) => t.geneCount), 1);

    return {
      data: top.map((t) => {
        const ratio = t.geneCount / maxGC;
        const label = t.termName || t.termId || "\u2014";
        return {
          name: truncateLabel(label),
          foldEnrichment: t.foldEnrichment,
          geneCount: t.geneCount,
          pValue: t.pValue,
          dotRadius: DOT_MIN_R + ratio * (DOT_MAX_R - DOT_MIN_R),
        };
      }),
      maxGeneCount: maxGC,
    };
  }, [terms]);

  const chartHeight = Math.max(data.length * 28 + 40, 140);

  return (
    <div className="border-b border-border/50 px-4 py-4">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Top {data.length} Terms by Significance
        </h4>
        <DotPlotLegend maxGeneCount={maxGeneCount} />
      </div>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          layout="vertical"
          data={data}
          margin={{ top: 4, right: 32, bottom: 16, left: 8 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="hsl(var(--border))"
            horizontal={false}
          />
          <XAxis
            type="number"
            dataKey="foldEnrichment"
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            label={{
              value: "Fold Enrichment",
              position: "insideBottom",
              offset: -8,
              fontSize: 11,
              fill: "hsl(var(--muted-foreground))",
            }}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={200}
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            content={<DotPlotTooltip />}
            cursor={{ fill: "hsl(var(--accent))", fillOpacity: 0.3 }}
          />
          <Bar
            dataKey="foldEnrichment"
            shape={<DotShape />}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
