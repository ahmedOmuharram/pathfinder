import { useState, useMemo, Fragment } from "react";
import type { EnrichmentResult, EnrichmentTerm } from "@pathfinder/shared";
import { AlertCircle, ArrowUpDown, ChevronRight } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { ENRICHMENT_ANALYSIS_LABELS, type SortDir } from "../constants";
import { Section } from "./Section";

type SortKey = "termName" | "geneCount" | "foldEnrichment" | "pValue" | "fdr";

const MAX_CHART_TERMS = 15;
const DOT_MIN_R = 4;
const DOT_MAX_R = 14;

interface EnrichmentSectionProps {
  results: EnrichmentResult[];
}

const analysisLabels = ENRICHMENT_ANALYSIS_LABELS;

/** Map -log10(pValue) onto a blue-to-red gradient for significance. */
function pvalColor(pValue: number): string {
  const negLog = -Math.log10(Math.max(pValue, 1e-20));
  const t = Math.min(negLog / 10, 1);
  const h = 220 - t * 220;
  return `hsl(${h}, ${70 + t * 10}%, ${55 - t * 5}%)`;
}

function fmtCount(n: number): string {
  return n.toLocaleString();
}

export function EnrichmentSection({ results }: EnrichmentSectionProps) {
  const [activeTab, setActiveTab] = useState(0);
  const [pThreshold, setPThreshold] = useState(0.05);
  const [prevResults, setPrevResults] = useState(results);

  if (results !== prevResults) {
    setPrevResults(results);
    setActiveTab(0);
  }

  const activeResult = results[activeTab];
  const filtered = useMemo(
    () => activeResult?.terms.filter((t) => t.pValue <= pThreshold) ?? [],
    [activeResult, pThreshold],
  );

  return (
    <Section title="Enrichment Analysis">
      <div className="rounded-lg border border-border bg-card">
        {/* Tab bar */}
        <div className="flex items-center gap-0 border-b border-border px-4">
          {results.map((r, i) => {
            const hasError = !!r.error;
            const count = r.terms.filter((t) => t.pValue <= pThreshold).length;
            return (
              <button
                key={r.analysisType}
                type="button"
                onClick={() => setActiveTab(i)}
                className={`relative flex items-center gap-1 px-3 py-2.5 text-xs font-medium transition ${
                  activeTab === i
                    ? "text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {hasError && (
                  <AlertCircle className="h-3 w-3 shrink-0 text-destructive" />
                )}
                {analysisLabels[r.analysisType] ?? r.analysisType}
                {!hasError && (
                  <span className="text-xs text-muted-foreground">{count}</span>
                )}
                {activeTab === i && (
                  <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-primary" />
                )}
              </button>
            );
          })}
          <div className="ml-auto flex items-center gap-2 py-2">
            <label className="text-xs text-muted-foreground">p &le;</label>
            <select
              value={pThreshold}
              onChange={(e) => setPThreshold(parseFloat(e.target.value))}
              className="rounded border border-border bg-card px-2 py-1 text-xs text-muted-foreground outline-none transition-colors duration-150"
            >
              <option value={0.001}>0.001</option>
              <option value={0.01}>0.01</option>
              <option value={0.05}>0.05</option>
              <option value={0.1}>0.1</option>
              <option value={1}>All</option>
            </select>
          </div>
        </div>

        {activeResult && activeResult.error && (
          <div className="flex items-center gap-2 px-5 py-6 text-xs text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>Analysis failed: {activeResult.error}</span>
          </div>
        )}
        {activeResult && !activeResult.error && (
          <>
            <SummaryBar result={activeResult} filteredCount={filtered.length} />
            {filtered.length > 0 && <EnrichmentDotPlot terms={filtered} />}
            <EnrichmentTable terms={filtered} />
          </>
        )}
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Summary statistics bar
// ---------------------------------------------------------------------------

function SummaryBar({
  result,
  filteredCount,
}: {
  result: EnrichmentResult;
  filteredCount: number;
}) {
  return (
    <div className="flex items-center gap-4 border-b border-border/50 bg-muted/30 px-4 py-2 text-xs text-muted-foreground">
      <span>
        <span className="font-medium text-foreground">{filteredCount}</span> significant
        term{filteredCount !== 1 ? "s" : ""}
      </span>
      {result.totalGenesAnalyzed > 0 && (
        <span>{fmtCount(result.totalGenesAnalyzed)} genes analyzed</span>
      )}
      {result.backgroundSize > 0 && (
        <span>background: {fmtCount(result.backgroundSize)}</span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Enrichment dot plot using Recharts BarChart (vertical layout)
// ---------------------------------------------------------------------------

interface DotChartDatum {
  name: string;
  foldEnrichment: number;
  geneCount: number;
  pValue: number;
  /** Pre-computed dot radius based on geneCount / maxGeneCount. */
  dotRadius: number;
}

/** Custom bar shape that renders a circle instead of a rectangle. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function DotShape(props: any) {
  const { x = 0, y = 0, width = 0, height = 0, payload } = props;
  if (!payload) return null;
  const d = payload as DotChartDatum;

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

function EnrichmentDotPlot({ terms }: { terms: EnrichmentTerm[] }) {
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
          name: label.length > 35 ? label.slice(0, 32) + "..." : label,
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
          <Bar dataKey="foldEnrichment" shape={<DotShape />} isAnimationActive={false}>
            {data.map((d, i) => (
              <Cell key={i} fill={pvalColor(d.pValue)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function DotPlotTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: DotChartDatum }>;
}) {
  if (!active || !payload?.[0]) return null;
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
// Enhanced sortable table with expandable rows
// ---------------------------------------------------------------------------

function EnrichmentTable({ terms }: { terms: EnrichmentTerm[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("pValue");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const sorted = useMemo(() => {
    const copy = [...terms];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "number" && typeof bv === "number") {
        return sortDir === "asc" ? av - bv : bv - av;
      }
      return sortDir === "asc"
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av));
    });
    return copy;
  }, [terms, sortKey, sortDir]);

  const toggle = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir(key === "termName" ? "asc" : "desc");
    }
  };

  const toggleExpand = (termId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(termId)) {
        next.delete(termId);
      } else {
        next.add(termId);
      }
      return next;
    });
  };

  if (terms.length === 0) {
    return (
      <div className="px-5 py-8 text-center text-xs text-muted-foreground">
        No enriched terms at this threshold.
      </div>
    );
  }

  const columns: { key: SortKey; label: string; align?: string }[] = [
    { key: "termName", label: "Term" },
    { key: "geneCount", label: "Genes", align: "text-right" },
    { key: "foldEnrichment", label: "Fold", align: "text-right" },
    { key: "pValue", label: "p-value", align: "text-right" },
    { key: "fdr", label: "FDR", align: "text-right" },
  ];

  return (
    <div className="max-h-96 overflow-y-auto">
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-card">
          <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
            <th className="w-6 px-2 py-2.5" />
            {columns.map((col) => (
              <th
                key={col.key}
                className={`cursor-pointer select-none px-4 py-2.5 font-medium transition-colors duration-150 ${col.align ?? ""}`}
                onClick={() => toggle(col.key)}
              >
                <span className="inline-flex items-center gap-1">
                  {col.label}
                  <ArrowUpDown className="h-2.5 w-2.5" />
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border/50">
          {sorted.map((t, idx) => {
            const rowKey = t.termId || `term-${idx}`;
            const expanded = expandedIds.has(rowKey);
            return (
              <Fragment key={rowKey}>
                <tr
                  className="cursor-pointer transition hover:bg-accent"
                  onClick={() => toggleExpand(rowKey)}
                >
                  <td className="px-2 py-2 text-muted-foreground">
                    <ChevronRight
                      className={`h-3 w-3 transition-transform duration-150 ${expanded ? "rotate-90" : ""}`}
                    />
                  </td>
                  <td className="max-w-xs truncate px-4 py-2 text-foreground">
                    {t.termId && (
                      <span className="mr-1.5 font-mono text-xs text-muted-foreground">
                        {t.termId}
                      </span>
                    )}
                    {t.termName || t.termId || "\u2014"}
                  </td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums text-muted-foreground">
                    {t.geneCount}
                  </td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums text-muted-foreground">
                    {t.foldEnrichment.toFixed(2)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums text-muted-foreground">
                    {t.pValue.toExponential(2)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums text-muted-foreground">
                    {t.fdr.toExponential(2)}
                  </td>
                </tr>
                {expanded && (
                  <tr>
                    <td colSpan={6} className="bg-muted/20 px-6 py-3">
                      <ExpandedTermDetails term={t} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Expanded row details (odds ratio, bonferroni, gene list)
// ---------------------------------------------------------------------------

function ExpandedTermDetails({ term }: { term: EnrichmentTerm }) {
  return (
    <div className="space-y-2 text-xs">
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-muted-foreground">
        <span>
          Background:{" "}
          <span className="font-mono text-foreground">
            {fmtCount(term.backgroundCount)}
          </span>
        </span>
        <span>
          Odds Ratio:{" "}
          <span className="font-mono text-foreground">{term.oddsRatio.toFixed(3)}</span>
        </span>
        <span>
          Bonferroni:{" "}
          <span className="font-mono text-foreground">
            {term.bonferroni.toExponential(2)}
          </span>
        </span>
      </div>

      {term.genes.length > 0 && (
        <div>
          <span className="text-muted-foreground">Genes ({term.genes.length}):</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {term.genes.map((gene) => (
              <span
                key={gene}
                className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-foreground"
              >
                {gene}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
