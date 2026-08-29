import { beforeEach, describe, expect, it } from "vitest";

import { loadOrSkip } from "./support";

interface EntityCount {
  entityId: string;
  entityDisplayName: string;
  count: number;
  unfilteredCount: number;
}

interface AnalysisPart {
  siteId: string;
  datasetId: string;
  studyId: string;
  analysisId: string;
  revision: number | null;
  studyDisplayName: string;
  displayName: string;
  numFilters: number;
  numComputations: number;
  filters: unknown[];
  filterSummaries: string[];
  entityCounts: EntityCount[];
  canExportRows: boolean;
}

interface SubsetPreviewPayload {
  datasetId: string;
  analysisId: string;
  entityCounts: EntityCount[];
  distribution: null;
}

interface VizPayload {
  datasetId: string;
  analysisId: string;
  chart: string;
  effectSizeLabel: string;
  effectSizeThreshold: number | null;
  significanceThreshold: number | null;
  effectDirection: string | null;
  totalPoints: number;
  retainedPoints: number;
  points: { pointId: string; effectSize: number; retained: boolean }[];
}

interface Thresholds {
  effectSizeThreshold: number;
  significanceThreshold: number;
  direction: string;
}

interface EdaState {
  binding: { siteId: string; datasetId: string; analysisId: string } | null;
  analysis: {
    analysisId: string;
    revision: number | null;
    displayName: string;
    filters: unknown[];
    unparsedFilterCount: number;
  } | null;
  subsetPreview: SubsetPreviewPayload | null;
  viz: Record<string, VizPayload | undefined>;
  jobs: Record<string, unknown>;
  volcanoThresholds: Thresholds;
  applyAnalysisState: (payload: AnalysisPart) => void;
  applySubsetPreview: (payload: SubsetPreviewPayload) => void;
  applyViz: (payload: VizPayload) => void;
  applyJob: (job: {
    jobId: string;
    taskId: string | null;
    appName: string;
    status: string;
  }) => void;
  setVolcanoThresholds: (thresholds: Thresholds) => void;
  reset: () => void;
}

type EdaStoreModule = { useEdaStore: { getState: () => EdaState } };

const storeModule = await loadOrSkip<EdaStoreModule>("@/state/eda");
const filterSchemaModule = await loadOrSkip<Record<string, unknown>>(
  "@pathfinder/shared/generated/zod/edaFilterSchema",
);

function eda(): EdaState {
  return (storeModule as EdaStoreModule).useEdaStore.getState();
}

const SAMPLE_COUNT: EntityCount = {
  entityId: "ENT_8151325d",
  entityDisplayName: "Sample",
  count: 6,
  unfilteredCount: 12,
};

const FEBRILE_FILTER = {
  entityId: "ENT_8151325d",
  variableId: "VAR_081ab087",
  type: "stringSet",
  stringSet: ["febrile"],
};

function analysisPart(overrides: Partial<AnalysisPart> = {}): AnalysisPart {
  return {
    siteId: "plasmodb",
    datasetId: "DS_e973eadd57",
    studyId: "STUDY_e973eadd57",
    analysisId: "acc-a1",
    revision: 0,
    studyDisplayName: "Heat shock response in sensitive mutants (LRR5, DHC)",
    displayName: "unnamed",
    numFilters: 0,
    numComputations: 0,
    filters: [],
    filterSummaries: [],
    entityCounts: [SAMPLE_COUNT],
    canExportRows: true,
    ...overrides,
  };
}

function revisionPart(revision: number | null, analysisId = "acc-a1"): AnalysisPart {
  return analysisPart({
    analysisId,
    revision,
    displayName: `${analysisId} at ${String(revision)}`,
  });
}

const PREVIEW: SubsetPreviewPayload = {
  datasetId: "DS_e973eadd57",
  analysisId: "acc-a1",
  entityCounts: [SAMPLE_COUNT],
  distribution: null,
};

const VOLCANO: VizPayload = {
  datasetId: "DS_e973eadd57",
  analysisId: "acc-a1",
  chart: "volcano",
  effectSizeLabel: "log2(Fold Change)",
  effectSizeThreshold: 2,
  significanceThreshold: 0.01,
  effectDirection: "upOnly",
  totalPoints: 5511,
  retainedPoints: 1543,
  points: [{ pointId: "PF3D7_0100200", effectSize: 3.94437533216012, retained: true }],
};

type SequencedPart = { analysisId: string; revision: number | null };

function seededRandom(seed: number): () => number {
  let state = seed;
  return () => {
    state = (state * 1103515245 + 12345) % 2147483648;
    return state / 2147483648;
  };
}

function shuffle(
  pool: readonly SequencedPart[],
  random: () => number,
): SequencedPart[] {
  const out = [...pool];
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    const held = out[i] as SequencedPart;
    out[i] = out[j] as SequencedPart;
    out[j] = held;
  }
  return out;
}

/** The rule the batch documents settle: newer revision wins, equal applies,
 * a null on either side is a last write, another analysis replaces. */
function referenceApply(
  held: SequencedPart | null,
  incoming: SequencedPart,
): SequencedPart {
  if (held === null) return incoming;
  if (held.analysisId !== incoming.analysisId) return incoming;
  if (held.revision === null || incoming.revision === null) return incoming;
  return incoming.revision >= held.revision ? incoming : held;
}

const PART_POOL: SequencedPart[] = ["acc-a1", "acc-a2"].flatMap((analysisId) => [
  ...[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((revision) => ({ analysisId, revision })),
  { analysisId, revision: null },
]);

describe.skipIf(storeModule === null)("the EDA store reconciles analysis parts", () => {
  beforeEach(() => {
    eda().reset();
  });

  it("ends on the newest revision when a replay arrives out of order", () => {
    for (const revision of [2, 1, 2, 3])
      eda().applyAnalysisState(revisionPart(revision));
    expect(eda().analysis?.displayName).toBe("acc-a1 at 3");
    expect(eda().analysis?.revision).toBe(3);
  });

  it("applies an equal revision, because a re-emit carries the same document", () => {
    eda().applyAnalysisState(revisionPart(2));
    eda().applyAnalysisState(analysisPart({ revision: 2, displayName: "re-emitted" }));
    expect(eda().analysis?.displayName).toBe("re-emitted");
  });

  it("takes the last write when the incoming part carries no revision", () => {
    eda().applyAnalysisState(revisionPart(4));
    eda().applyAnalysisState(revisionPart(null));
    expect(eda().analysis?.displayName).toBe("acc-a1 at null");
    expect(eda().analysis?.revision).toBe(null);
  });

  it("takes the last write when the held state carries no revision", () => {
    eda().applyAnalysisState(revisionPart(null));
    eda().applyAnalysisState(revisionPart(1));
    expect(eda().analysis?.displayName).toBe("acc-a1 at 1");
    expect(eda().analysis?.revision).toBe(1);
  });

  it("replaces wholesale on another analysis and drops preview, plots and jobs", () => {
    eda().applyAnalysisState(revisionPart(5));
    eda().applySubsetPreview(PREVIEW);
    eda().applyViz(VOLCANO);
    eda().applyJob({
      jobId: "db04204e5386396e1ca2cb78469ab6fb",
      taskId: null,
      appName: "differentialexpression",
      status: "complete",
    });
    eda().applyAnalysisState(revisionPart(0, "acc-a2"));
    expect(eda().analysis?.analysisId).toBe("acc-a2");
    expect(eda().analysis?.revision).toBe(0);
    expect(eda().binding?.analysisId).toBe("acc-a2");
    expect(eda().subsetPreview).toBe(null);
    expect(eda().viz).toEqual({});
    expect(eda().jobs).toEqual({});
  });

  it("ratchets the revision forward and follows every switch, over 100 replays", () => {
    const random = seededRandom(0x5eed1);
    for (let iteration = 0; iteration < 100; iteration += 1) {
      eda().reset();
      const sequence = shuffle(PART_POOL, random).slice(0, 8);
      let held: SequencedPart | null = null;
      let heldBeforeLast: SequencedPart | null = null;
      let resetIndex = 0;
      for (let index = 0; index < sequence.length; index += 1) {
        const part = sequence[index] as SequencedPart;
        heldBeforeLast = held;
        const next = referenceApply(held, part);
        const switched = held?.analysisId !== next.analysisId;
        if (switched || part.revision === null) resetIndex = index;
        held = next;
        eda().applyAnalysisState(analysisPart(part));
      }
      const expected = held as SequencedPart;
      expect(eda().analysis?.analysisId).toBe(expected.analysisId);
      expect(eda().analysis?.revision).toBe(expected.revision);
      expect(eda().binding?.analysisId).toBe(expected.analysisId);
      const ceiling = expected.revision;
      if (ceiling !== null) {
        for (const part of sequence.slice(resetIndex + 1)) {
          expect(part.analysisId).toBe(expected.analysisId);
          expect(part.revision === null || part.revision <= ceiling).toBe(true);
        }
      }
      const last = sequence[sequence.length - 1] as SequencedPart;
      if ((heldBeforeLast?.analysisId ?? last.analysisId) !== last.analysisId) {
        expect(expected.analysisId).toBe(last.analysisId);
        expect(expected.revision).toBe(last.revision);
      }
    }
  });
});

describe.skipIf(storeModule === null || filterSchemaModule === null)(
  "the store parses each wire filter and counts what the schema refuses",
  () => {
    it("hydrates one parsed filter and counts the entry it cannot parse", () => {
      eda().reset();
      eda().applyAnalysisState(
        analysisPart({
          numFilters: 2,
          filters: [FEBRILE_FILTER, { type: "notAFilter", stringSet: 7 }],
          filterSummaries: ["temperature_condition is febrile"],
        }),
      );
      expect(eda().analysis?.filters).toHaveLength(1);
      expect(eda().analysis?.unparsedFilterCount).toBe(1);
    });
  },
);

describe.skipIf(storeModule === null)(
  "the volcano thresholds follow the researcher",
  () => {
    beforeEach(() => {
      eda().reset();
      eda().applyAnalysisState(analysisPart({ revision: 1 }));
    });

    it("adopts the thresholds the first viz payload carries", () => {
      eda().applyViz(VOLCANO);
      expect(eda().volcanoThresholds).toEqual({
        effectSizeThreshold: 2,
        significanceThreshold: 0.01,
        direction: "upOnly",
      });
    });

    it("keeps an edited threshold when a second payload arrives", () => {
      eda().applyViz(VOLCANO);
      eda().setVolcanoThresholds({
        effectSizeThreshold: 5,
        significanceThreshold: 0.001,
        direction: "downOnly",
      });
      eda().applyViz({ ...VOLCANO, retainedPoints: 1200 });
      expect(eda().volcanoThresholds).toEqual({
        effectSizeThreshold: 5,
        significanceThreshold: 0.001,
        direction: "downOnly",
      });
      expect(eda().viz["volcano"]?.retainedPoints).toBe(1200);
    });
  },
);
