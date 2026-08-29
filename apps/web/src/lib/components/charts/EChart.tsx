"use client";

import { useState } from "react";
import type { EChartsType } from "echarts/core";
import type { EChartsOption } from "echarts";

import { initChart } from "./echartsRegistry";

export interface EChartProps {
  option: EChartsOption;
  height: number;
  ariaLabel: string;
  testId: string;
}

export function EChart({ option, height, ariaLabel, testId }: EChartProps) {
  const [instance, setInstance] = useState<EChartsType | null>(null);
  const [applied, setApplied] = useState<EChartsOption | null>(null);

  // The ref callback closes over setters only, so its identity is stable and
  // React never re-attaches it.
  const [mount] = useState(() => (node: HTMLDivElement | null) => {
    if (node === null) return undefined;
    const chart = initChart(node);
    setInstance(chart);
    const observer = new ResizeObserver(() => {
      if (!chart.isDisposed()) chart.resize();
    });
    observer.observe(node);
    return () => {
      observer.disconnect();
      chart.dispose();
      setInstance(null);
      setApplied(null);
    };
  });

  if (instance !== null && applied !== option) {
    setApplied(option);
    queueMicrotask(() => {
      if (!instance.isDisposed()) instance.setOption(option, { notMerge: true });
    });
  }

  return (
    <div
      ref={mount}
      data-testid={testId}
      role="img"
      aria-label={ariaLabel}
      style={{ height }}
      className="w-full"
    />
  );
}
