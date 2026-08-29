import { describe, expect, it } from "vitest";

import { loadOrSkip } from "./support";

interface VolcanoPoint {
  pointId: string;
  effectSize: number;
  pValue?: number | null;
  adjustedPValue?: number | null;
}

type Thresholds = {
  effectSizeThreshold: number;
  significanceThreshold: number;
  direction: "upOnly" | "downOnly" | "upAndDown";
};

interface Selection {
  up: string[];
  down: string[];
  selected: string[];
  droppedRowCount: number;
}

type SelectionModule = {
  selectVolcanoGenes: (
    points: readonly VolcanoPoint[],
    thresholds: Thresholds,
    significanceField: "adjustedPValue" | "pValue",
  ) => Selection;
};

const selectionModule = await loadOrSkip<SelectionModule>("@/lib/eda/volcanoSelection");

function select(
  points: readonly VolcanoPoint[],
  thresholds: Thresholds,
  field: "adjustedPValue" | "pValue" = "adjustedPValue",
): Selection {
  return (selectionModule as SelectionModule).selectVolcanoGenes(
    points,
    thresholds,
    field,
  );
}

/** Ten genes at the live thresholds. Two rows carry no adjusted p-value: one
 * omits the key, as one live row of 5511 did, and one sends null. */
const CLOUD: VolcanoPoint[] = [
  { pointId: "PF3D7_0930300", effectSize: 2.5, pValue: 0.0002, adjustedPValue: 0.001 },
  { pointId: "PF3D7_1133400", effectSize: 1, pValue: 0.01, adjustedPValue: 0.049 },
  {
    pointId: "PF3D7_0207600",
    effectSize: 3.94437533216012,
    pValue: 1.95781599815607e-5,
    adjustedPValue: 0.000137772236907279,
  },
  { pointId: "PF3D7_0417200", effectSize: -2.5, pValue: 0.001, adjustedPValue: 0.004 },
  { pointId: "PF3D7_0709000", effectSize: -1.6, pValue: 0.004, adjustedPValue: 0.02 },
  {
    pointId: "PF3D7_1222600",
    effectSize: 0.9,
    pValue: 0.00001,
    adjustedPValue: 0.0001,
  },
  {
    pointId: "PF3D7_0100100",
    effectSize: -0.218035922112735,
    pValue: 0.350285751849808,
    adjustedPValue: 0.46960449943855,
  },
  { pointId: "PF3D7_1343700", effectSize: 4.2, pValue: 0.02, adjustedPValue: 0.05 },
  { pointId: "PF3D7_0523000", effectSize: -3.1, pValue: 0.03, adjustedPValue: null },
  { pointId: "PF3D7_MIT04200", effectSize: -1.49447459261845 },
];

const LIVE: Thresholds = {
  effectSizeThreshold: 1,
  significanceThreshold: 0.05,
  direction: "upAndDown",
};

const UP = ["PF3D7_0930300", "PF3D7_1133400", "PF3D7_0207600"];
const DOWN = ["PF3D7_0417200", "PF3D7_0709000"];

function seededRandom(seed: number): () => number {
  let state = seed;
  return () => {
    state = (state * 1103515245 + 12345) % 2147483648;
    return state / 2147483648;
  };
}

function randomCloud(random: () => number, size: number): VolcanoPoint[] {
  const points: VolcanoPoint[] = [];
  for (let i = 0; i < size; i += 1) {
    const effectSize = Math.round((random() * 12 - 6) * 1000) / 1000;
    const significance = Math.round(random() * 1000) / 1000;
    const shape = random();
    if (shape < 0.1) points.push({ pointId: `G${String(i)}`, effectSize });
    else if (shape < 0.2) {
      points.push({ pointId: `G${String(i)}`, effectSize, adjustedPValue: null });
    } else {
      points.push({
        pointId: `G${String(i)}`,
        effectSize,
        adjustedPValue: significance,
      });
    }
  }
  return points;
}

function byId(points: readonly VolcanoPoint[]): Map<string, VolcanoPoint> {
  return new Map(points.map((point) => [point.pointId, point]));
}

describe.skipIf(selectionModule === null)(
  "the volcano selection at the live thresholds",
  () => {
    it("splits the cloud into three genes up and two down", () => {
      const result = select(CLOUD, LIVE);
      expect(result.up).toEqual(UP);
      expect(result.down).toEqual(DOWN);
      expect(result.selected).toEqual([...UP, ...DOWN]);
    });

    it("selects only the up genes for upOnly", () => {
      expect(select(CLOUD, { ...LIVE, direction: "upOnly" }).selected).toEqual(UP);
    });

    it("selects only the down genes for downOnly", () => {
      expect(select(CLOUD, { ...LIVE, direction: "downOnly" }).selected).toEqual(DOWN);
    });

    it("drops both rows without an adjusted p-value and counts them", () => {
      const result = select(CLOUD, LIVE);
      expect(result.droppedRowCount).toBe(2);
      expect(result.selected).not.toContain("PF3D7_MIT04200");
      expect(result.selected).not.toContain("PF3D7_0523000");
    });

    it("keeps the effect size inclusive and the significance strict", () => {
      const result = select(CLOUD, LIVE);
      expect(result.selected).toContain("PF3D7_1133400");
      expect(result.selected).not.toContain("PF3D7_1343700");
      expect(result.selected).not.toContain("PF3D7_1222600");
    });

    it("selects on the raw p-value when asked, which admits two more genes", () => {
      const result = select(CLOUD, LIVE, "pValue");
      expect(result.up).toEqual([...UP, "PF3D7_1343700"]);
      expect(result.down).toEqual([...DOWN, "PF3D7_0523000"]);
      expect(result.droppedRowCount).toBe(1);
    });
  },
);

const GRID = [0.5, 1, 1.5, 2, 3, 4.5];

describe.skipIf(selectionModule === null)(
  "the volcano selection over random clouds",
  () => {
    it("never grows the selection when the effect-size threshold rises", () => {
      const random = seededRandom(0xc10d);
      for (let iteration = 0; iteration < 50; iteration += 1) {
        const points = randomCloud(random, 12);
        const significanceThreshold = Math.round(random() * 500) / 1000;
        let previous: string[] | null = null;
        for (const effectSizeThreshold of GRID) {
          const result = select(points, {
            effectSizeThreshold,
            significanceThreshold,
            direction: "upAndDown",
          });
          if (previous !== null) {
            expect(result.selected.length <= previous.length).toBe(true);
            for (const id of result.selected) expect(previous).toContain(id);
          }
          previous = result.selected;
        }
      }
    });

    it("partitions the upAndDown selection into the up and down halves", () => {
      const random = seededRandom(0xf00d);
      for (let iteration = 0; iteration < 50; iteration += 1) {
        const points = randomCloud(random, 12);
        const thresholds: Thresholds = {
          effectSizeThreshold: GRID[iteration % GRID.length] ?? 1,
          significanceThreshold: Math.round(random() * 500) / 1000,
          direction: "upAndDown",
        };
        const both = select(points, thresholds);
        const up = select(points, { ...thresholds, direction: "upOnly" });
        const down = select(points, { ...thresholds, direction: "downOnly" });
        expect([...up.selected, ...down.selected].sort()).toEqual(
          [...both.selected].sort(),
        );
        expect(up.selected.filter((id) => down.selected.includes(id))).toEqual([]);
        expect(both.up).toEqual(up.selected);
        expect(both.down).toEqual(down.selected);
      }
    });

    it("returns only points that pass both inequalities", () => {
      const random = seededRandom(0xbeef);
      for (let iteration = 0; iteration < 50; iteration += 1) {
        const points = randomCloud(random, 12);
        const thresholds: Thresholds = {
          effectSizeThreshold: GRID[iteration % GRID.length] ?? 1,
          significanceThreshold: Math.round(random() * 500) / 1000,
          direction: "upAndDown",
        };
        const result = select(points, thresholds);
        const index = byId(points);
        for (const id of result.selected) {
          const point = index.get(id) as VolcanoPoint;
          const significance = point.adjustedPValue;
          expect(significance === null || significance === undefined).toBe(false);
          expect(Math.abs(point.effectSize) >= thresholds.effectSizeThreshold).toBe(
            true,
          );
          expect((significance ?? 1) < thresholds.significanceThreshold).toBe(true);
        }
        for (const id of result.up)
          expect((index.get(id)?.effectSize ?? 0) > 0).toBe(true);
        for (const id of result.down) {
          expect((index.get(id)?.effectSize ?? 0) < 0).toBe(true);
        }
      }
    });
  },
);
