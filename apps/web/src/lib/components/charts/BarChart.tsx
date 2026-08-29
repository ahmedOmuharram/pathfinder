"use client";

import type { EChartsOption } from "echarts";

import { EChart } from "./EChart";
import { buildCategoryOption } from "./category.options";
import { readChartTokens } from "./chartTheme";
import type { EdaCategorySeries } from "./types";

export interface BarChartProps {
  series: readonly EdaCategorySeries[];
  barMode: "group" | "stack";
  valueLabel: string;
  height: number;
  testId: string;
}

export function BarChart(props: BarChartProps) {
  const model = buildCategoryOption({
    series: props.series,
    stacked: props.barMode === "stack",
    valueLabel: props.valueLabel,
    tokens: readChartTokens(),
  });

  const option: EChartsOption = {
    animation: false,
    grid: { left: 52, right: 16, top: 24, bottom: 40 },
    xAxis: { type: "category", data: model.categories, axisTick: { show: false } },
    yAxis: {
      type: "value",
      name: model.valueLabel,
      nameLocation: "middle",
      nameGap: 38,
    },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    ...(model.series.length > 1
      ? { legend: { top: 0, right: 0, icon: "circle" } }
      : {}),
    series: model.series.map((s) => ({
      type: "bar" as const,
      name: s.name,
      data: s.values,
      barCategoryGap: "30%",
      itemStyle: { color: s.color },
      ...(s.stack !== null ? { stack: s.stack } : {}),
    })),
  };

  return (
    <EChart
      option={option}
      height={props.height}
      ariaLabel={`Counts over ${String(model.categories.length)} categories`}
      testId={props.testId}
    />
  );
}
