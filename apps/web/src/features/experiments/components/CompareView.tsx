import { useMemo } from "react";
import type { Experiment, ExperimentMetrics } from "@pathfinder/shared";
import { useExperimentStore } from "../store";
import { ArrowLeft } from "lucide-react";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

function pct(v: number | null | undefined): string {
  if (v == null) return "\u2014";
  return `${(v * 100).toFixed(1)}%`;
}

interface CompareViewProps {
  experimentA: Experiment;
  experimentB: Experiment;
}

export function CompareView({ experimentA, experimentB }: CompareViewProps) {
  const { clearCompare } = useExperimentStore();
  const ma = experimentA.metrics;
  const mb = experimentB.metrics;

  if (!ma || !mb) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-slate-500">
        Both experiments must have completed metrics to compare.
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-8 px-8 py-6">
        <header>
          <button
            type="button"
            onClick={clearCompare}
            className="mb-3 inline-flex items-center gap-1.5 text-xs text-slate-400 transition hover:text-slate-600"
          >
            <ArrowLeft className="h-3 w-3" />
            Back to results
          </button>
          <h1 className="text-xl font-semibold tracking-tight text-slate-900">
            Experiment Comparison
          </h1>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <ExperimentLabel label="A" experiment={experimentA} />
            <ExperimentLabel label="B" experiment={experimentB} />
          </div>
        </header>

        <MetricsComparison
          ma={ma}
          mb={mb}
          nameA={experimentA.config.name}
          nameB={experimentB.config.name}
        />

        <ConfusionComparison a={experimentA} b={experimentB} />

        <ParameterDiff a={experimentA} b={experimentB} />
      </div>
    </div>
  );
}

function ExperimentLabel({
  label,
  experiment,
}: {
  label: string;
  experiment: Experiment;
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-4 py-2.5">
      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 items-center justify-center rounded bg-slate-100 text-[10px] font-bold text-slate-500">
          {label}
        </span>
        <span className="truncate text-[13px] font-medium text-slate-800">
          {experiment.config.name}
        </span>
      </div>
      <div className="mt-1 pl-7 text-[11px] text-slate-400">
        {experiment.config.searchName}
      </div>
    </div>
  );
}

type MetricRow = {
  label: string;
  key: string;
  getter: (m: ExperimentMetrics) => number;
  invert?: boolean;
};

const METRICS: MetricRow[] = [
  { label: "Sensitivity", key: "sensitivity", getter: (m) => m.sensitivity },
  { label: "Specificity", key: "specificity", getter: (m) => m.specificity },
  { label: "Precision", key: "precision", getter: (m) => m.precision },
  { label: "F1 Score", key: "f1", getter: (m) => m.f1Score },
  { label: "MCC", key: "mcc", getter: (m) => m.mcc },
  {
    label: "Balanced Accuracy",
    key: "balAcc",
    getter: (m) => m.balancedAccuracy,
  },
  { label: "NPV", key: "npv", getter: (m) => m.negativePredictiveValue },
  {
    label: "FPR",
    key: "fpr",
    getter: (m) => m.falsePositiveRate,
    invert: true,
  },
  {
    label: "FNR",
    key: "fnr",
    getter: (m) => m.falseNegativeRate,
    invert: true,
  },
  { label: "Youden\u2019s J", key: "youdens", getter: (m) => m.youdensJ },
];

function MetricsComparison({
  ma,
  mb,
  nameA,
  nameB,
}: {
  ma: ExperimentMetrics;
  mb: ExperimentMetrics;
  nameA: string;
  nameB: string;
}) {
  void nameA;
  void nameB;

  const radarData = useMemo(() => {
    const keys: { label: string; getter: (m: ExperimentMetrics) => number }[] = [
      { label: "Sensitivity", getter: (m) => m.sensitivity },
      { label: "Specificity", getter: (m) => m.specificity },
      { label: "Precision", getter: (m) => m.precision },
      { label: "F1", getter: (m) => m.f1Score },
      { label: "Bal. Acc.", getter: (m) => m.balancedAccuracy },
    ];
    return keys.map((k) => ({
      metric: k.label,
      A: +(k.getter(ma) * 100).toFixed(1),
      B: +(k.getter(mb) * 100).toFixed(1),
    }));
  }, [ma, mb]);

  return (
    <section>
      <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-slate-400">
        Classification Metrics
      </h2>
      <div className="rounded-lg border border-slate-200 bg-white">
        <div className="grid grid-cols-[1fr_300px] divide-x divide-slate-200 max-lg:grid-cols-1 max-lg:divide-x-0 max-lg:divide-y">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-[10px] uppercase tracking-wider text-slate-400">
                <th className="px-5 py-2.5 text-left font-medium">Metric</th>
                <th className="px-5 py-2.5 text-right font-medium">A</th>
                <th className="px-5 py-2.5 text-right font-medium">B</th>
                <th className="px-5 py-2.5 text-right font-medium">&Delta;</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {METRICS.map((row) => {
                const a = row.getter(ma);
                const b = row.getter(mb);
                const diff = a - b;
                const better = row.invert ? diff < 0 : diff > 0;
                const worse = row.invert ? diff > 0 : diff < 0;
                const deltaColor =
                  Math.abs(diff) < 0.001
                    ? "text-slate-400"
                    : better
                      ? "text-slate-900 font-semibold"
                      : worse
                        ? "text-slate-400"
                        : "text-slate-400";
                return (
                  <tr key={row.key}>
                    <td className="px-5 py-2 text-slate-600">{row.label}</td>
                    <td className="px-5 py-2 text-right font-mono tabular-nums text-slate-700">
                      {pct(a)}
                    </td>
                    <td className="px-5 py-2 text-right font-mono tabular-nums text-slate-700">
                      {pct(b)}
                    </td>
                    <td
                      className={`px-5 py-2 text-right font-mono tabular-nums ${deltaColor}`}
                    >
                      {diff > 0 ? "+" : ""}
                      {pct(diff)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <div className="flex items-center justify-center p-4 max-lg:py-6">
            <ResponsiveContainer width="100%" height={260}>
              <RadarChart data={radarData} outerRadius="72%">
                <PolarGrid stroke="#e2e8f0" />
                <PolarAngleAxis
                  dataKey="metric"
                  tick={{ fontSize: 10, fill: "#94a3b8" }}
                />
                <PolarRadiusAxis
                  angle={90}
                  domain={[0, 100]}
                  tick={{ fontSize: 9, fill: "#cbd5e1" }}
                  tickCount={5}
                />
                <Radar
                  name="A"
                  dataKey="A"
                  stroke="#1e293b"
                  fill="#1e293b"
                  fillOpacity={0.08}
                  strokeWidth={1.5}
                />
                <Radar
                  name="B"
                  dataKey="B"
                  stroke="#94a3b8"
                  fill="#94a3b8"
                  fillOpacity={0.06}
                  strokeWidth={1.5}
                  strokeDasharray="4 3"
                />
                <Legend
                  wrapperStyle={{ fontSize: 10, color: "#64748b" }}
                  iconSize={8}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </section>
  );
}

function ConfusionComparison({ a, b }: { a: Experiment; b: Experiment }) {
  if (!a.metrics || !b.metrics) return null;
  const cmA = a.metrics.confusionMatrix;
  const cmB = b.metrics.confusionMatrix;

  const barData = [
    { label: "TP", A: cmA.truePositives, B: cmB.truePositives },
    { label: "FP", A: cmA.falsePositives, B: cmB.falsePositives },
    { label: "FN", A: cmA.falseNegatives, B: cmB.falseNegatives },
    { label: "TN", A: cmA.trueNegatives, B: cmB.trueNegatives },
  ];

  return (
    <section>
      <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-slate-400">
        Confusion Matrix
      </h2>
      <div className="grid grid-cols-[1fr_1fr] gap-4 max-md:grid-cols-1">
        <MiniCM label={a.config.name} cm={cmA} tag="A" />
        <MiniCM label={b.config.name} cm={cmB} tag="B" />
      </div>
      <div className="mt-4 rounded-lg border border-slate-200 bg-white p-5">
        <div className="mb-3 text-xs font-medium text-slate-500">Count Comparison</div>
        <ResponsiveContainer width="100%" height={140}>
          <BarChart data={barData} margin={{ top: 0, right: 0, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11, fill: "#64748b" }}
              axisLine={{ stroke: "#e2e8f0" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 10, fill: "#94a3b8" }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                fontSize: 11,
                border: "1px solid #e2e8f0",
                borderRadius: 6,
                boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
              }}
            />
            <Bar dataKey="A" fill="#1e293b" radius={[2, 2, 0, 0]} barSize={20} />
            <Bar dataKey="B" fill="#94a3b8" radius={[2, 2, 0, 0]} barSize={20} />
            <Legend wrapperStyle={{ fontSize: 10, color: "#64748b" }} iconSize={8} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function MiniCM({
  label,
  cm,
  tag,
}: {
  label: string;
  cm: {
    truePositives: number;
    falsePositives: number;
    falseNegatives: number;
    trueNegatives: number;
  };
  tag: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className="flex h-5 w-5 items-center justify-center rounded bg-slate-100 text-[10px] font-bold text-slate-500">
          {tag}
        </span>
        <span className="truncate text-xs font-medium text-slate-700">{label}</span>
      </div>
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded border border-slate-200 bg-slate-200 text-center text-[13px]">
        <div className="bg-slate-50 px-3 py-3">
          <div className="font-semibold tabular-nums text-slate-900">
            {cm.truePositives}
          </div>
          <div className="mt-0.5 text-[10px] text-slate-400">TP</div>
        </div>
        <div className="bg-white px-3 py-3">
          <div className="font-semibold tabular-nums text-slate-900">
            {cm.falseNegatives}
          </div>
          <div className="mt-0.5 text-[10px] text-slate-400">FN</div>
        </div>
        <div className="bg-white px-3 py-3">
          <div className="font-semibold tabular-nums text-slate-900">
            {cm.falsePositives}
          </div>
          <div className="mt-0.5 text-[10px] text-slate-400">FP</div>
        </div>
        <div className="bg-slate-50 px-3 py-3">
          <div className="font-semibold tabular-nums text-slate-900">
            {cm.trueNegatives}
          </div>
          <div className="mt-0.5 text-[10px] text-slate-400">TN</div>
        </div>
      </div>
    </div>
  );
}

function ParameterDiff({ a, b }: { a: Experiment; b: Experiment }) {
  const allKeys = useMemo(() => {
    const keys = new Set([
      ...Object.keys(a.config.parameters),
      ...Object.keys(b.config.parameters),
    ]);
    return Array.from(keys);
  }, [a.config.parameters, b.config.parameters]);

  if (allKeys.length === 0) return null;

  return (
    <section>
      <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-slate-400">
        Parameter Differences
      </h2>
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-slate-200 text-[10px] uppercase tracking-wider text-slate-400">
              <th className="px-5 py-2.5 text-left font-medium">Parameter</th>
              <th className="px-5 py-2.5 text-center font-medium">A</th>
              <th className="px-5 py-2.5 text-center font-medium">B</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {allKeys.map((key) => {
              const vA = String(a.config.parameters[key] ?? "\u2014");
              const vB = String(b.config.parameters[key] ?? "\u2014");
              const isDiff = vA !== vB;
              return (
                <tr key={key} className={isDiff ? "bg-slate-50/60" : ""}>
                  <td className="px-5 py-2 font-medium text-slate-600">{key}</td>
                  <td className="px-5 py-2 text-center font-mono tabular-nums text-slate-700">
                    {vA}
                  </td>
                  <td className="px-5 py-2 text-center font-mono tabular-nums text-slate-700">
                    {vB}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
