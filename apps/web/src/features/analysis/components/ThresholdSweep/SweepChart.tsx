import { Loader2 } from "lucide-react";
import type { ThresholdSweepPoint } from "@/features/workbench/api";
import { CHART_COLORS } from "@/lib/utils/chartTheme";
import { fmtNum, truncateLabel } from "./types";

const W = 600;
const H = 260;
const PAD = { top: 20, right: 20, bottom: 40, left: 50 };
const plotW = W - PAD.left - PAD.right;
const plotH = H - PAD.top - PAD.bottom;

const Y_TICKS = [0, 0.25, 0.5, 0.75, 1.0];

function y(v: number) {
  return PAD.top + plotH - v * plotH;
}

export function SweepChart({
  points,
  parameter,
  sweepType,
  formatValue,
  isStreaming,
}: {
  points: ThresholdSweepPoint[];
  parameter: string;
  sweepType: "numeric" | "categorical";
  formatValue: (v: number | string) => string;
  isStreaming: boolean;
}) {
  if (sweepType === "categorical") {
    return (
      <CategoricalChart
        points={points}
        parameter={parameter}
        formatValue={formatValue}
        isStreaming={isStreaming}
      />
    );
  }

  return (
    <NumericChart points={points} parameter={parameter} isStreaming={isStreaming} />
  );
}

function CategoricalChart({
  points,
  parameter,
  formatValue,
  isStreaming,
}: {
  points: ThresholdSweepPoint[];
  parameter: string;
  formatValue: (v: number | string) => string;
  isStreaming: boolean;
}) {
  const spacing = points.length > 1 ? plotW / (points.length - 1) : plotW / 2;
  const xCat = (i: number) => PAD.left + (points.length > 1 ? i * spacing : plotW / 2);

  const makeLineCat = (getter: (p: ThresholdSweepPoint) => number) =>
    points
      .map(
        (p, i) =>
          `${i === 0 ? "M" : "L"}${xCat(i).toFixed(1)},${y(getter(p)).toFixed(1)}`,
      )
      .join(" ");

  const sensLine = makeLineCat((p) => p.metrics!.sensitivity);
  const specLine = makeLineCat((p) => p.metrics!.specificity);
  const f1Line = makeLineCat((p) => p.metrics!.f1Score);

  return (
    <ChartWrapper parameter={parameter} isStreaming={isStreaming}>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: H }}>
        <YGrid />
        {points.map((p, i) => (
          <text
            key={String(p.value)}
            x={xCat(i)}
            y={H - PAD.bottom + 16}
            textAnchor="middle"
            className="fill-muted-foreground"
            style={{ fontSize: 8 }}
          >
            {truncateLabel(formatValue(p.value), 12)}
          </text>
        ))}
        <XAxisLabel parameter={parameter} />
        <MetricPaths sensLine={sensLine} specLine={specLine} f1Line={f1Line} />
        {points.map((p, i) => (
          <MetricDots
            key={String(p.value)}
            cx={xCat(i)}
            sensitivity={p.metrics!.sensitivity}
            specificity={p.metrics!.specificity}
            f1Score={p.metrics!.f1Score}
          />
        ))}
      </svg>
      <ChartLegend />
    </ChartWrapper>
  );
}

function NumericChart({
  points,
  parameter,
  isStreaming,
}: {
  points: ThresholdSweepPoint[];
  parameter: string;
  isStreaming: boolean;
}) {
  const numValues = points.map((p) => Number(p.value));
  const xMin = Math.min(...numValues);
  const xMax = Math.max(...numValues);
  const xRange = xMax - xMin || 1;
  const x = (v: number) => PAD.left + ((v - xMin) / xRange) * plotW;

  const makeLine = (getter: (p: ThresholdSweepPoint) => number) =>
    points
      .map(
        (p, i) =>
          `${i === 0 ? "M" : "L"}${x(Number(p.value)).toFixed(1)},${y(getter(p)).toFixed(1)}`,
      )
      .join(" ");

  const sensLine = makeLine((p) => p.metrics!.sensitivity);
  const specLine = makeLine((p) => p.metrics!.specificity);
  const f1Line = makeLine((p) => p.metrics!.f1Score);

  const xTicks = points.filter(
    (_, i) =>
      i === 0 || i === points.length - 1 || i % Math.ceil(points.length / 6) === 0,
  );

  return (
    <ChartWrapper parameter={parameter} isStreaming={isStreaming}>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: H }}>
        <YGrid />
        {xTicks.map((p) => (
          <text
            key={String(p.value)}
            x={x(Number(p.value))}
            y={H - PAD.bottom + 16}
            textAnchor="middle"
            className="fill-muted-foreground"
            style={{ fontSize: 9 }}
          >
            {fmtNum(Number(p.value))}
          </text>
        ))}
        <XAxisLabel parameter={parameter} />
        <MetricPaths sensLine={sensLine} specLine={specLine} f1Line={f1Line} />
        {points.map((p) => (
          <MetricDots
            key={String(p.value)}
            cx={x(Number(p.value))}
            sensitivity={p.metrics!.sensitivity}
            specificity={p.metrics!.specificity}
            f1Score={p.metrics!.f1Score}
          />
        ))}
      </svg>
      <ChartLegend />
    </ChartWrapper>
  );
}

function YGrid() {
  return (
    <>
      {Y_TICKS.map((v) => (
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
            x={PAD.left - 6}
            y={y(v) + 3}
            textAnchor="end"
            className="fill-muted-foreground"
            style={{ fontSize: 9 }}
          >
            {(v * 100).toFixed(0)}%
          </text>
        </g>
      ))}
    </>
  );
}

function XAxisLabel({ parameter }: { parameter: string }) {
  return (
    <text
      x={PAD.left + plotW / 2}
      y={H - 4}
      textAnchor="middle"
      className="fill-muted-foreground"
      style={{ fontSize: 10 }}
    >
      {parameter}
    </text>
  );
}

function MetricPaths({
  sensLine,
  specLine,
  f1Line,
}: {
  sensLine: string;
  specLine: string;
  f1Line: string;
}) {
  return (
    <>
      <path d={sensLine} fill="none" stroke={CHART_COLORS.primary} strokeWidth={2} />
      <path
        d={specLine}
        fill="none"
        stroke={CHART_COLORS.destructive}
        strokeWidth={2}
      />
      <path
        d={f1Line}
        fill="none"
        stroke="hsl(var(--foreground))"
        strokeWidth={2}
        strokeDasharray="4 2"
      />
    </>
  );
}

function MetricDots({
  cx,
  sensitivity,
  specificity,
  f1Score,
}: {
  cx: number;
  sensitivity: number;
  specificity: number;
  f1Score: number;
}) {
  return (
    <g>
      <circle cx={cx} cy={y(sensitivity)} r={2.5} fill={CHART_COLORS.primary} />
      <circle cx={cx} cy={y(specificity)} r={2.5} fill={CHART_COLORS.destructive} />
      <circle cx={cx} cy={y(f1Score)} r={2} fill="hsl(var(--foreground))" />
    </g>
  );
}

function ChartWrapper({
  parameter,
  isStreaming,
  children,
}: {
  parameter: string;
  isStreaming: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
        Metrics vs {parameter}
        {isStreaming && (
          <span className="flex items-center gap-1 text-primary">
            <Loader2 className="h-3 w-3 animate-spin" />
            streaming
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

function ChartLegend() {
  return (
    <div className="mt-2 flex justify-center gap-6 text-xs text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-0.5 w-4 rounded bg-[hsl(var(--chart-1))]" />
        Sensitivity
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-0.5 w-4 rounded bg-[hsl(var(--chart-4))]" />
        Specificity
      </span>
      <span className="flex items-center gap-1.5">
        <span
          className="inline-block h-0.5 w-4 rounded border-t border-dashed border-foreground bg-transparent"
          style={{ borderTopWidth: 2 }}
        />
        F1
      </span>
    </div>
  );
}
