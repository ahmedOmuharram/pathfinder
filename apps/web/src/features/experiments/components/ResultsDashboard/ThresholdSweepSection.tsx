import { useState, useMemo, useCallback } from "react";
import type { Experiment } from "@pathfinder/shared";
import { Play, Loader2 } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { runThresholdSweep, type ThresholdSweepResult } from "../../api";
import { pct } from "./utils";

interface ThresholdSweepSectionProps {
  experiment: Experiment;
}

export function ThresholdSweepSection({ experiment }: ThresholdSweepSectionProps) {
  const [paramName, setParamName] = useState("");
  const [minVal, setMinVal] = useState("");
  const [maxVal, setMaxVal] = useState("");
  const [steps, setSteps] = useState("10");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ThresholdSweepResult | null>(null);

  const numericParams = useMemo(() => {
    const params = experiment.config.parameters;
    if (!params || typeof params !== "object") return [];
    return Object.entries(params)
      .filter(([, v]) => !isNaN(Number(v)) && v !== "")
      .map(([k, v]) => ({ name: k, currentValue: Number(v) }));
  }, [experiment.config.parameters]);

  const handleRun = useCallback(async () => {
    const mn = parseFloat(minVal);
    const mx = parseFloat(maxVal);
    const st = parseInt(steps);
    if (!paramName || isNaN(mn) || isNaN(mx) || mn >= mx || isNaN(st)) return;

    setLoading(true);
    setError(null);
    try {
      const res = await runThresholdSweep(
        experiment.id,
        paramName,
        mn,
        mx,
        Math.max(3, Math.min(50, st)),
      );
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
    setLoading(false);
  }, [experiment.id, paramName, minVal, maxVal, steps]);

  if (numericParams.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-muted/30 px-5 py-8 text-center text-sm text-muted-foreground">
        No numeric parameters detected in this experiment&apos;s configuration.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        Sweep a numeric parameter across a range to visualize the
        sensitivity/specificity trade-off.
      </p>

      <div className="grid grid-cols-4 gap-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">
            Parameter
          </label>
          <select
            value={paramName}
            onChange={(e) => {
              setParamName(e.target.value);
              const p = numericParams.find((np) => np.name === e.target.value);
              if (p) {
                const cv = p.currentValue;
                setMinVal(String(Math.max(0, cv * 0.2)));
                setMaxVal(String(cv * 3));
              }
            }}
            className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">Select…</option>
            {numericParams.map((np) => (
              <option key={np.name} value={np.name}>
                {np.name} (current: {np.currentValue})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">
            Min
          </label>
          <input
            type="number"
            value={minVal}
            onChange={(e) => setMinVal(e.target.value)}
            className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">
            Max
          </label>
          <input
            type="number"
            value={maxVal}
            onChange={(e) => setMaxVal(e.target.value)}
            className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">
            Steps
          </label>
          <input
            type="number"
            min={3}
            max={50}
            value={steps}
            onChange={(e) => setSteps(e.target.value)}
            className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      <Button
        size="sm"
        onClick={handleRun}
        disabled={loading || !paramName || !minVal || !maxVal}
        loading={loading}
      >
        <Play className="h-3.5 w-3.5" />
        {loading ? "Running…" : "Run Sweep"}
      </Button>

      {error && <p className="text-xs text-destructive">{error}</p>}

      {result && <SweepChart result={result} />}
    </div>
  );
}

function SweepChart({ result }: { result: ThresholdSweepResult }) {
  const validPoints = result.points.filter((p) => p.metrics != null);

  if (validPoints.length < 2) {
    return (
      <p className="text-xs text-muted-foreground">
        Not enough valid data points to render a chart.
      </p>
    );
  }

  const W = 600;
  const H = 260;
  const PAD = { top: 20, right: 20, bottom: 40, left: 50 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  const xMin = Math.min(...validPoints.map((p) => p.value));
  const xMax = Math.max(...validPoints.map((p) => p.value));
  const xRange = xMax - xMin || 1;

  const x = (v: number) => PAD.left + ((v - xMin) / xRange) * plotW;
  const y = (v: number) => PAD.top + plotH - v * plotH;

  const makeLine = (getter: (p: (typeof validPoints)[0]) => number) =>
    validPoints
      .map(
        (p, i) =>
          `${i === 0 ? "M" : "L"}${x(p.value).toFixed(1)},${y(getter(p)).toFixed(1)}`,
      )
      .join(" ");

  const sensLine = makeLine((p) => p.metrics!.sensitivity);
  const specLine = makeLine((p) => p.metrics!.specificity);
  const f1Line = makeLine((p) => p.metrics!.f1Score);

  const yTicks = [0, 0.25, 0.5, 0.75, 1.0];
  const xTicks = validPoints.filter(
    (_, i) =>
      i === 0 ||
      i === validPoints.length - 1 ||
      i % Math.ceil(validPoints.length / 6) === 0,
  );

  return (
    <div>
      <div className="mb-2 text-xs font-medium text-muted-foreground">
        Metrics vs {result.parameter}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: H }}>
        {yTicks.map((v) => (
          <g key={v}>
            <line
              x1={PAD.left}
              y1={y(v)}
              x2={W - PAD.right}
              y2={y(v)}
              stroke="#e2e8f0"
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
        {xTicks.map((p) => (
          <text
            key={p.value}
            x={x(p.value)}
            y={H - PAD.bottom + 16}
            textAnchor="middle"
            className="fill-muted-foreground"
            style={{ fontSize: 9 }}
          >
            {Number.isInteger(p.value) ? p.value : p.value.toFixed(2)}
          </text>
        ))}
        <text
          x={PAD.left + plotW / 2}
          y={H - 4}
          textAnchor="middle"
          className="fill-muted-foreground"
          style={{ fontSize: 10 }}
        >
          {result.parameter}
        </text>

        <path d={sensLine} fill="none" stroke="#2563eb" strokeWidth={2} />
        <path d={specLine} fill="none" stroke="#dc2626" strokeWidth={2} />
        <path
          d={f1Line}
          fill="none"
          stroke="#1e293b"
          strokeWidth={2}
          strokeDasharray="4 2"
        />

        {validPoints.map((p) => (
          <g key={p.value}>
            <circle
              cx={x(p.value)}
              cy={y(p.metrics!.sensitivity)}
              r={2.5}
              fill="#2563eb"
            />
            <circle
              cx={x(p.value)}
              cy={y(p.metrics!.specificity)}
              r={2.5}
              fill="#dc2626"
            />
            <circle cx={x(p.value)} cy={y(p.metrics!.f1Score)} r={2} fill="#1e293b" />
          </g>
        ))}
      </svg>
      <div className="mt-2 flex justify-center gap-6 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4 rounded bg-blue-600" />
          Sensitivity
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4 rounded bg-red-600" />
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

      <div className="mt-4 max-h-40 overflow-y-auto rounded-md border border-border">
        <table className="w-full text-left text-xs">
          <thead className="sticky top-0 bg-card">
            <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
              <th className="px-3 py-2 font-medium">{result.parameter}</th>
              <th className="px-3 py-2 font-medium">Sensitivity</th>
              <th className="px-3 py-2 font-medium">Specificity</th>
              <th className="px-3 py-2 font-medium">F1</th>
              <th className="px-3 py-2 font-medium">Results</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {validPoints.map((p) => (
              <tr key={p.value}>
                <td className="px-3 py-1.5 font-mono text-foreground">{p.value}</td>
                <td className="px-3 py-1.5 font-mono text-muted-foreground">
                  {pct(p.metrics!.sensitivity)}
                </td>
                <td className="px-3 py-1.5 font-mono text-muted-foreground">
                  {pct(p.metrics!.specificity)}
                </td>
                <td className="px-3 py-1.5 font-mono text-muted-foreground">
                  {pct(p.metrics!.f1Score)}
                </td>
                <td className="px-3 py-1.5 font-mono text-muted-foreground">
                  {p.metrics!.totalResults}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
