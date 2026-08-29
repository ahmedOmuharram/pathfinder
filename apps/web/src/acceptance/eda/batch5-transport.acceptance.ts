/**
 * @vitest-environment jsdom
 */
import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
} from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { loadOrSkip } from "./support";

interface PatchResponse {
  analysis: { revision: number | null; canExportRows: boolean } | null;
  job: { jobId: string; taskId: string | null; status: string } | null;
  step: { rootStepId: string } | null;
}

interface VizResponse {
  chart: string;
  totalPoints: number;
  retainedPoints: number;
  points: { pointId: string; effectSize: number; pValue?: number | null }[];
}

interface DistributionResponse {
  variableId: string;
  labels: string[];
  values: number[];
  subsetSize: number;
  numVarValues: number;
  isMultiValued: boolean;
}

type EdaApiModule = {
  patchConversationEda: (id: string, body: unknown) => Promise<PatchResponse>;
  edaViz: (body: unknown) => Promise<VizResponse>;
  edaDistribution: (body: unknown) => Promise<DistributionResponse>;
};

const BASE = "http://localhost:3000";
const PATCH_URL = `${BASE}/api/v1/conversations/conv-acc/eda`;
const server = setupServer();
const apiModule = await loadOrSkip<EdaApiModule>("@/lib/api/eda");

function api(): EdaApiModule {
  return apiModule as EdaApiModule;
}

const ANALYSIS = {
  siteId: "plasmodb",
  datasetId: "DS_e973eadd57",
  studyId: "STUDY_e973eadd57",
  analysisId: "a-1",
  revision: 4,
  studyDisplayName: "Heat shock response in sensitive mutants (LRR5, DHC)",
  displayName: "Febrile samples",
  numFilters: 1,
  numComputations: 0,
  filters: [
    {
      entityId: "ENT_8151325d",
      variableId: "VAR_081ab087",
      type: "stringSet",
      stringSet: ["febrile"],
    },
  ],
  filterSummaries: ["temperature_condition is febrile"],
  entityCounts: [
    {
      entityId: "ENT_8151325d",
      entityDisplayName: "Sample",
      count: 6,
      unfilteredCount: 12,
    },
  ],
  canExportRows: true,
};

const COMPUTATION = {
  type: "differentialexpression",
  configuration: {
    identifierVariable: { entityId: "ENT_fd574cd6", variableId: "VEUPATHDB_GENE_ID" },
    valueVariable: {
      entityId: "ENT_fd574cd6",
      variableId: "SEQUENCE_READ_COUNT_SENSE",
    },
    comparator: {
      variable: { entityId: "ENT_8151325d", variableId: "VAR_081ab087" },
      groupA: [{ label: "normal" }],
      groupB: [{ label: "febrile" }],
    },
    differentialExpressionMethod: "DESeq",
    pValueFloor: "1e-200",
  },
};

const ACTIONS: { name: string; body: Record<string, unknown> }[] = [
  {
    name: "bind",
    body: { action: "bind", siteId: "plasmodb", datasetId: "DS_e973eadd57" },
  },
  { name: "set-filters", body: { action: "set-filters", filters: ANALYSIS.filters } },
  { name: "run-compute", body: { action: "run-compute", computation: COMPUTATION } },
  {
    name: "export-step",
    body: {
      action: "export-step",
      thresholds: {
        effectSizeThreshold: 1,
        significanceThreshold: 0.05,
        effectDirection: "upAndDown",
      },
    },
  },
  { name: "unbind", body: { action: "unbind" } },
];

const EMPTY_ENVELOPE = { analysis: null, job: null, step: null };

let sentBodies: string[] = [];

function capturePatch(response: Record<string, unknown>): void {
  server.use(
    http.patch(PATCH_URL, async ({ request }) => {
      sentBodies.push(await request.text());
      return HttpResponse.json(response);
    }),
  );
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  sentBodies = [];
});

describe.skipIf(apiModule === null)(
  "the conversation EDA patch sends each action verbatim",
  () => {
    it.each(ACTIONS)("sends the $name action with no added field", async ({ body }) => {
      capturePatch(EMPTY_ENVELOPE);
      await api().patchConversationEda("conv-acc", body);
      expect(sentBodies).toHaveLength(1);
      expect(JSON.parse(sentBodies[0] as string)).toEqual(body);
      expect(Object.keys(JSON.parse(sentBodies[0] as string) as object).sort()).toEqual(
        Object.keys(body).sort(),
      );
    });

    it("sends unbind as exactly one key", async () => {
      capturePatch(EMPTY_ENVELOPE);
      await api().patchConversationEda("conv-acc", { action: "unbind" });
      expect(sentBodies[0]).toBe('{"action":"unbind"}');
    });

    it("spells the exported direction effectDirection, not direction", async () => {
      capturePatch(EMPTY_ENVELOPE);
      await api().patchConversationEda("conv-acc", ACTIONS[3]?.body);
      const sent = JSON.parse(sentBodies[0] as string) as {
        thresholds: Record<string, unknown>;
      };
      expect(Object.keys(sent.thresholds).sort()).toEqual([
        "effectDirection",
        "effectSizeThreshold",
        "significanceThreshold",
      ]);
      expect(sent.thresholds["effectDirection"]).toBe("upAndDown");
    });

    it("repeats an identical run-compute byte for byte, which is the status poll", async () => {
      capturePatch({
        analysis: null,
        job: {
          jobId: "db04204e5386396e1ca2cb78469ab6fb",
          taskId: null,
          appName: "differentialexpression",
          status: "in-progress",
        },
        step: null,
      });
      const body = { action: "run-compute", computation: COMPUTATION };
      const first = await api().patchConversationEda("conv-acc", body);
      const second = await api().patchConversationEda("conv-acc", body);
      expect(sentBodies[0]).toBe(sentBodies[1]);
      expect(first.job?.jobId).toBe("db04204e5386396e1ca2cb78469ab6fb");
      expect(second.job?.taskId).toBe(null);
      expect(second.job?.status).toBe("in-progress");
    });
  },
);

describe.skipIf(apiModule === null)(
  "the conversation EDA patch parses its envelope",
  () => {
    it("accepts an envelope whose three members are null", async () => {
      capturePatch(EMPTY_ENVELOPE);
      const result = await api().patchConversationEda("conv-acc", { action: "unbind" });
      expect(result.analysis).toBe(null);
      expect(result.job).toBe(null);
      expect(result.step).toBe(null);
    });

    it("accepts a full analysis payload and keeps its revision", async () => {
      capturePatch({ analysis: ANALYSIS, job: null, step: null });
      const result = await api().patchConversationEda("conv-acc", {
        action: "set-filters",
        filters: ANALYSIS.filters,
      });
      expect(result.analysis?.revision).toBe(4);
      expect(result.analysis?.canExportRows).toBe(true);
    });

    it("refuses an envelope with no analysis key", async () => {
      capturePatch({ job: null, step: null });
      await expect(
        api().patchConversationEda("conv-acc", { action: "unbind" }),
      ).rejects.toThrow();
    });
  },
);

const VOLCANO = {
  datasetId: "DS_e973eadd57",
  analysisId: "a-1",
  chart: "volcano",
  effectSizeLabel: "log2(Fold Change)",
  effectSizeThreshold: 1,
  significanceThreshold: 0.05,
  effectDirection: "upAndDown",
  totalPoints: 5511,
  retainedPoints: 1543,
  points: [
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
      pointId: "PF3D7_MIT04200",
      effectSize: -1.49447459261845,
      pValue: null,
      adjustedPValue: null,
      retained: false,
    },
  ],
};

/** The live Species distribution: multi-valued, so the bars outnumber the rows. */
const SPECIES = {
  variableId: "VAR_035294d0",
  variableDisplayName: "Species",
  labels: ["P. berghei", "P. falciparum", "P. yoelii"],
  values: [4011, 4130, 268],
  subsetSize: 4279,
  numVarValues: 8409,
  numMissingCases: 0,
  isMultiValued: true,
};

describe.skipIf(apiModule === null)(
  "the EDA read routes round-trip their payloads",
  () => {
    it("keeps the volcano counts and the row that carries no p-value", async () => {
      server.use(http.post(`${BASE}/api/v1/eda/viz`, () => HttpResponse.json(VOLCANO)));
      const result = await api().edaViz({
        siteId: "plasmodb",
        datasetId: "DS_e973eadd57",
        chart: "volcano",
      });
      expect(result.chart).toBe("volcano");
      expect(result.totalPoints).toBe(5511);
      expect(result.retainedPoints).toBe(1543);
      expect(result.points).toHaveLength(3);
      expect(result.points[2]?.pointId).toBe("PF3D7_MIT04200");
      expect(result.points[2]?.pValue ?? null).toBe(null);
      expect(result.points[1]?.effectSize).toBe(3.94437533216012);
    });

    it("keeps the distribution arrays aligned and its multi-valued statistics", async () => {
      server.use(
        http.post(`${BASE}/api/v1/eda/distribution`, () => HttpResponse.json(SPECIES)),
      );
      const result = await api().edaDistribution({
        siteId: "plasmodb",
        datasetId: "DS_e973eadd57",
        entityId: "GENE_PHENOTYPE_DATA_ENTITY",
        variableId: "VAR_035294d0",
        filters: [],
      });
      expect(result.labels).toHaveLength(result.values.length);
      expect(result.values).toEqual([4011, 4130, 268]);
      expect(result.values.reduce((sum, value) => sum + value, 0)).toBe(
        result.numVarValues,
      );
      expect(result.subsetSize).toBe(4279);
      expect(result.isMultiValued).toBe(true);
    });
  },
);
