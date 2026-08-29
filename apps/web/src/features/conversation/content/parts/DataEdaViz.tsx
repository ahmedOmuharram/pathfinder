"use client";

import { useState } from "react";
import { ChevronsDownUp, ChevronsUpDown } from "lucide-react";
import type { EdaViz } from "@pathfinder/shared";

import { Button } from "@/components/ui/button";
import { ScatterChart } from "@/lib/components/charts/ScatterChart";
import { VolcanoChart } from "@/lib/components/charts/VolcanoChart";
import type {
  EdaScatterSeries,
  VolcanoThresholds,
} from "@/lib/components/charts/types";
import { selectVolcanoGenes } from "@/lib/eda/volcanoSelection";
import { useEdaStore, useHydrateEdaPart } from "@/state/eda";

const COLLAPSED_HEIGHT = 220;
const EXPANDED_HEIGHT = 480;
const GENE_LIST_LIMIT = 12;
const SIGNIFICANCE_FIELD = "adjustedPValue";
const READOUT = "mt-1 text-[11px] text-muted-foreground";

export function DataEdaViz({ data }: { data: EdaViz }) {
  useHydrateEdaPart({ kind: "viz", data });
  const thresholds = useEdaStore((s) => s.volcanoThresholds);
  const [expanded, setExpanded] = useState(false);
  const height = expanded ? EXPANDED_HEIGHT : COLLAPSED_HEIGHT;

  return (
    <div
      data-testid="data-eda-viz"
      className="my-2 rounded-md border border-border bg-card p-3"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium">{data.effectSizeLabel}</span>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label={expanded ? "Collapse plot" : "Expand plot"}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? (
            <ChevronsDownUp className="size-3.5" aria-hidden />
          ) : (
            <ChevronsUpDown className="size-3.5" aria-hidden />
          )}
        </Button>
      </div>
      <VizBody data={data} height={height} thresholds={thresholds} />
    </div>
  );
}

interface VizBodyProps {
  data: EdaViz;
  height: number;
  thresholds: VolcanoThresholds;
}

function VizBody({ data, height, thresholds }: VizBodyProps) {
  if (data.points.length === 0) {
    return (
      <p data-testid="data-eda-viz-empty" className={READOUT}>
        This compute returned no points.
      </p>
    );
  }
  switch (data.chart) {
    case "volcano":
      return <VolcanoBody data={data} height={height} thresholds={thresholds} />;
    case "scatter":
      return <ScatterBody data={data} height={height} />;
    case "histogram":
    case "bar":
    case "boxplot":
      return (
        <p data-testid="data-eda-viz-unsupported-chart" className={READOUT}>
          {`${data.chart} plots are not available from this compute, which returns one point per gene.`}
        </p>
      );
  }
}

function VolcanoBody({ data, height, thresholds }: VizBodyProps) {
  const { selected } = selectVolcanoGenes(data.points, thresholds, SIGNIFICANCE_FIELD);
  const listed = selected.slice(0, GENE_LIST_LIMIT);
  const hidden = selected.length - listed.length;

  return (
    <>
      <VolcanoChart
        points={data.points}
        thresholds={thresholds}
        significanceField={SIGNIFICANCE_FIELD}
        effectSizeLabel={data.effectSizeLabel}
        height={height}
        testId="eda-viz-volcano"
      />
      <p data-testid="eda-viz-volcano-selection" className={READOUT}>
        {`${selected.length.toLocaleString()} ${selected.length === 1 ? "gene" : "genes"} selected at these thresholds - ${data.retainedPoints.toLocaleString()} of ${data.totalPoints.toLocaleString()} retained by the compute`}
      </p>
      {listed.length > 0 ? (
        <p data-testid="eda-viz-volcano-genes" className={READOUT}>
          {hidden > 0
            ? `${listed.join(", ")} and ${hidden.toLocaleString()} more`
            : listed.join(", ")}
        </p>
      ) : null}
    </>
  );
}

/** One scatter series in volcano coordinates. A point with no usable p-value
 * has no y and is left out. */
function scatterSeries(data: EdaViz): EdaScatterSeries {
  const x: number[] = [];
  const y: number[] = [];
  const pointIds: string[] = [];
  for (const point of data.points) {
    const pValue = point.pValue;
    if (pValue === null || !Number.isFinite(pValue) || pValue <= 0) continue;
    x.push(point.effectSize);
    y.push(-Math.log10(pValue));
    pointIds.push(point.pointId);
  }
  return { name: "Genes", x, y, pointIds };
}

function ScatterBody({ data, height }: { data: EdaViz; height: number }) {
  const series = scatterSeries(data);
  return (
    <>
      <ScatterChart
        series={[series]}
        xAxis={{ variableId: "effectSize", displayName: data.effectSizeLabel }}
        yAxis={{ variableId: "pValue", displayName: "-log10(p-value)" }}
        height={height}
        testId="eda-viz-scatter"
      />
      <p data-testid="eda-viz-scatter-count" className={READOUT}>
        {`${series.x.length.toLocaleString()} of ${data.totalPoints.toLocaleString()} points plotted`}
      </p>
    </>
  );
}
