"use client";

import { useMemo, useCallback, useEffect, useState } from "react";
import { VennDiagram, VennSeries, VennArc, VennLabel, ChartTooltip } from "reaviz";
import {
  computeVennData,
  computeExclusiveRegions,
  logScaleVennData,
  type VennInput,
} from "@/lib/utils/vennData";

const CHART_VARS = ["--chart-1", "--chart-2", "--chart-3", "--chart-4", "--chart-5"];
const FALLBACK_COLORS = ["#2563eb", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed"];

/** Resolve CSS custom properties to actual color strings D3/chroma can parse. */
function resolveChartColors(): string[] {
  if (typeof document === "undefined") return FALLBACK_COLORS;
  const style = getComputedStyle(document.documentElement);
  return CHART_VARS.map((v, i) => {
    const raw = style.getPropertyValue(v).trim();
    return raw !== "" ? `hsl(${raw})` : (FALLBACK_COLORS[i] ?? "#2563eb");
  });
}

type VennLayoutItem = {
  data: { key: string; sets: string[]; size: number };
  text: { x: number; y: number };
  [k: string]: unknown;
};

interface SetVennProps {
  sets: VennInput[];
  height?: number;
  width?: number;
  onRegionClick?: (geneIds: string[], label: string) => void;
}

export function SetVenn({
  sets,
  height = 240,
  width = 380,
  onRegionClick,
}: SetVennProps) {
  const [colors, setColors] = useState(FALLBACK_COLORS);
  useEffect(() => {
    queueMicrotask(() => setColors(resolveChartColors()));
  }, []);

  // Real counts for display, log-scaled data for circle sizing
  const realData = useMemo(() => computeVennData(sets), [sets]);
  const data = useMemo(() => logScaleVennData(realData), [realData]);

  // Lookup: joined key → real gene count
  const realCountMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const d of realData) {
      map.set(d.key.join("|"), d.data);
    }
    return map;
  }, [realData]);

  // Total unique genes across all sets (for percentage calculation)
  const totalGenes = useMemo(() => {
    const all = new Set<string>();
    for (const s of sets) {
      for (const g of s.geneIds) all.add(g);
    }
    return all.size;
  }, [sets]);

  // Format label: show real count and percentage
  const formatLabel = useCallback(
    (d: VennLayoutItem) => {
      const realCount = realCountMap.get(d.data.key) ?? Math.round(d.data.size);
      const pct = totalGenes > 0 ? ((realCount / totalGenes) * 100).toFixed(1) : "0.0";
      return `${realCount.toLocaleString()} (${pct}%)`;
    },
    [realCountMap, totalGenes],
  );

  // Format tooltip: show set name(s) with real count
  const formatTooltip = useCallback(
    (d: { x: string; y: number }) => {
      const key = d.x.replace(/ \| /g, "|");
      const realCount = realCountMap.get(key) ?? Math.round(d.y);
      return `${d.x}: ${realCount.toLocaleString()}`;
    },
    [realCountMap],
  );

  const exclusiveRegions = useMemo(
    () => (onRegionClick ? computeExclusiveRegions(sets) : null),
    [sets, onRegionClick],
  );

  const handleArcClick = useCallback(
    (event: { value: { sets: string[]; size: number }; nativeEvent: MouseEvent }) => {
      if (!onRegionClick || !exclusiveRegions) return;
      const regionKey = event.value.sets.join(",");
      const geneIds = exclusiveRegions.get(regionKey) ?? [];
      const label =
        event.value.sets.length === 1
          ? `Only ${event.value.sets[0]}`
          : event.value.sets.join(" \u2229 ");
      onRegionClick(geneIds, label);
    },
    [onRegionClick, exclusiveRegions],
  );

  return (
    <div className="flex flex-col items-center gap-1">
      <VennDiagram
        type="euler"
        height={height}
        width={width}
        data={data}
        series={
          <VennSeries
            colorScheme={colors.slice(0, sets.length)}
            label={<VennLabel labelType="value" showAll format={formatLabel} />}
            arc={
              <VennArc
                strokeWidth={1.5}
                {...(onRegionClick != null ? { onClick: handleArcClick } : {})}
                style={{ cursor: onRegionClick != null ? "pointer" : "default" }}
                tooltip={<ChartTooltip content={formatTooltip} />}
              />
            }
          />
        }
      />
      {onRegionClick && (
        <p className="text-[10px] text-muted-foreground">
          Click a region to create a gene set
        </p>
      )}
    </div>
  );
}
