"use client";

import type { EdaDistributionSeries, EdaSubsetPreview } from "@pathfinder/shared";

import { HistogramChart } from "@/lib/components/charts/HistogramChart";
import { Figure } from "@/lib/components/thread/Figure";
import { useHydrateEdaPart } from "@/state/eda";

import { entityCountCaption } from "./entityCounts";

const HISTOGRAM_HEIGHT = 72;
const MUTED = "text-[11px] text-muted-foreground";
const MULTIVALUED_NOTE =
  "one record can carry several values, so these counts do not add up to the subset size";

function variableName(series: EdaDistributionSeries): string {
  return series.variableDisplayName.length > 0
    ? series.variableDisplayName
    : series.variableId;
}

export function DataEdaSubsetPreview({ data }: { data: EdaSubsetPreview }) {
  useHydrateEdaPart({ kind: "subset-preview", data });
  const note = data.distributionNote ?? "";
  const series = data.distribution;
  const counts = entityCountCaption(data.entityCounts);

  return (
    <Figure
      testId="data-eda-subset-preview"
      title={series !== null ? variableName(series) : null}
      caption={
        series !== null
          ? `${counts}, ${series.numVarValues.toLocaleString()} values`
          : counts
      }
    >
      <div className="text-xs">
        <ul className={MUTED}>
          {data.entityCounts.map((entity) => (
            <li key={entity.entityId}>
              {`${entity.count.toLocaleString()} of ${entity.unfilteredCount.toLocaleString()} ${
                entity.entityDisplayName.length > 0
                  ? entity.entityDisplayName
                  : entity.entityId
              }`}
            </li>
          ))}
        </ul>
        {series !== null ? <Distribution series={series} /> : null}
        {note.length > 0 ? (
          <p data-testid="data-eda-subset-note" className={`mt-1 ${MUTED}`}>
            {note}
          </p>
        ) : null}
      </div>
    </Figure>
  );
}

function Distribution({ series }: { series: EdaDistributionSeries }) {
  const name = variableName(series);

  return (
    <div className="mt-2">
      <HistogramChart
        series={[{ name, labels: series.labels, values: series.values }]}
        barMode="stack"
        valueLabel="Records"
        height={HISTOGRAM_HEIGHT}
        testId="data-eda-subset-histogram"
        ariaLabel={`${name} distribution over the subset`}
      />
      <ul className={`mt-1 flex flex-wrap gap-x-3 ${MUTED}`}>
        {series.labels.map((label, index) => (
          <li key={label} data-testid={`data-eda-subset-bin-${String(index)}`}>
            {`${label} ${(series.values[index] ?? 0).toLocaleString()}`}
          </li>
        ))}
      </ul>
      <p data-testid="data-eda-subset-coverage" className={`mt-1 ${MUTED}`}>
        {`${String(series.numVarValues)} of ${String(series.subsetSize)} records have a value`}
        {series.numMissingCases > 0
          ? `, ${String(series.numMissingCases)} missing`
          : ""}
      </p>
      {series.isMultiValued ? (
        <p data-testid="data-eda-subset-multivalued" className={`mt-1 ${MUTED}`}>
          {MULTIVALUED_NOTE}
        </p>
      ) : null}
    </div>
  );
}
