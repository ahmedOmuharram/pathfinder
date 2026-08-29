import type {
  VolcanoPointInput,
  VolcanoSignificanceField,
  VolcanoThresholds,
} from "@/lib/components/charts/types";

/** One point per gene, from a recorded differentialexpression result. The
 * retained flag is the backend's answer at 1 and 0.05 on the adjusted p-value. */
export const VOLCANO_POINT_SAMPLE: readonly (VolcanoPointInput & {
  retained: boolean;
})[] = [
  {
    pointId: "PF3D7_0100100",
    effectSize: -0.218035922112735,
    pValue: 0.350285751849808,
    adjustedPValue: 0.46960449943855,
    retained: false,
  },
  {
    pointId: "PF3D7_0100200",
    effectSize: 3.94437533216012,
    pValue: 1.95781599815607e-5,
    adjustedPValue: 0.000137772236907279,
    retained: true,
  },
  {
    pointId: "PF3D7_0100300",
    effectSize: -2.5,
    pValue: 0.001,
    adjustedPValue: 0.004,
    retained: true,
  },
  {
    pointId: "PF3D7_0100400",
    effectSize: 0.4,
    pValue: 0.0001,
    adjustedPValue: 0.0009,
    retained: false,
  },
  {
    pointId: "PF3D7_0100500",
    effectSize: 1.2,
    pValue: 0.2,
    adjustedPValue: 0.4,
    retained: false,
  },
  { pointId: "PF3D7_MIT04200", effectSize: -1.49447459261845, retained: false },
];

export interface VolcanoSelection {
  up: string[];
  down: string[];
  selected: string[];
  droppedRowCount: number;
}

function finite(raw: number | null | undefined): number | null {
  if (raw === null || raw === undefined) return null;
  return Number.isFinite(raw) ? raw : null;
}

export function selectVolcanoGenes(
  points: readonly VolcanoPointInput[],
  thresholds: VolcanoThresholds,
  significanceField: VolcanoSignificanceField,
): VolcanoSelection {
  const up: string[] = [];
  const down: string[] = [];
  let droppedRowCount = 0;

  for (const point of points) {
    const effect = finite(point.effectSize);
    const significance = finite(point[significanceField]);
    if (effect === null || significance === null) {
      droppedRowCount += 1;
      continue;
    }
    if (Math.abs(effect) < thresholds.effectSizeThreshold) continue;
    if (significance >= thresholds.significanceThreshold) continue;
    if (effect > 0) up.push(point.pointId);
    else down.push(point.pointId);
  }

  const selected =
    thresholds.direction === "upOnly"
      ? [...up]
      : thresholds.direction === "downOnly"
        ? [...down]
        : [...up, ...down];
  return { up, down, selected, droppedRowCount };
}
