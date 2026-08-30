import { Loader2 } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import type { ThresholdSweepPoint } from "@/lib/api/analysis";
import { readChartRoleColors } from "@/lib/utils/chartTheme";
import { fmtNum, truncateLabel } from "./types";

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
  const chartColors = readChartRoleColors();
  const chartData = points.map((p) => ({
    label:
      sweepType === "categorical"
        ? truncateLabel(formatValue(p.value), 12)
        : fmtNum(Number(p.value)),
    value: p.value,
    sensitivity: p.metrics?.sensitivity ?? 0,
    specificity: p.metrics?.specificity ?? 0,
    f1: p.metrics?.f1Score ?? 0,
  }));

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
      <ResponsiveContainer width="100%" height={260}>
        <LineChart
          data={chartData}
          margin={{ top: 10, right: 20, bottom: 20, left: 10 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="hsl(var(--border))"
            strokeOpacity={0.5}
          />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }}
            label={{
              value: parameter,
              position: "insideBottom",
              offset: -10,
              style: { fontSize: 10, fill: "hsl(var(--muted-foreground))" },
            }}
          />
          <YAxis
            domain={[0, 1]}
            ticks={[0, 0.25, 0.5, 0.75, 1.0]}
            tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
            tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }}
            width={45}
          />
          <Tooltip
            contentStyle={{
              fontSize: 11,
              background: "hsl(var(--popover))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 6,
              color: "hsl(var(--popover-foreground))",
            }}
            formatter={(value, name) => [
              `${(Number(value) * 100).toFixed(1)}%`,
              String(name),
            ]}
          />
          <Legend
            wrapperStyle={{ fontSize: 11, color: "hsl(var(--muted-foreground))" }}
          />
          <Line
            type="monotone"
            dataKey="sensitivity"
            name="Sensitivity"
            stroke={chartColors.primary}
            strokeWidth={2}
            dot={{ r: 2.5 }}
            activeDot={{ r: 4 }}
          />
          <Line
            type="monotone"
            dataKey="specificity"
            name="Specificity"
            stroke={chartColors.destructive}
            strokeWidth={2}
            dot={{ r: 2.5 }}
            activeDot={{ r: 4 }}
          />
          <Line
            type="monotone"
            dataKey="f1"
            name="F1"
            stroke="hsl(var(--foreground))"
            strokeWidth={2}
            strokeDasharray="4 2"
            dot={{ r: 2 }}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
