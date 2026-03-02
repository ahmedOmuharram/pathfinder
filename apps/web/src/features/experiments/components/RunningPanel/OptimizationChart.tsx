/**
 * Lightweight SVG sparkline for the running-panel sidebar.
 *
 * This is intentionally separate from the Recharts-based
 * `features/chat/components/optimization/OptimizationChart.tsx` which renders a
 * full interactive chart with tooltips, early-stop reference areas, and a
 * responsive container. The two components share the same conceptual data
 * (optimization trial scores) but differ fundamentally in rendering approach
 * (raw SVG vs Recharts), size budget, and interactivity requirements -- merging
 * them would add more complexity than it removes.
 */
import type { TrialHistoryEntry } from "../../store";

export function OptimizationChart({ trials }: { trials: TrialHistoryEntry[] }) {
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
