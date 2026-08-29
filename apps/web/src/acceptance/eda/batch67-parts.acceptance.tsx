/**
 * @vitest-environment jsdom
 */
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import { loadOrSkip } from "./support";

vi.mock("@/lib/components/charts/echartsRegistry", () => ({
  initChart: () => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: () => false,
  }),
}));

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

interface PreviewPart {
  datasetId: string;
  analysisId: string;
  entityCounts: EntityCount[];
  distribution: {
    variableId: string;
    variableDisplayName: string;
    labels: string[];
    values: number[];
    subsetSize: number;
    numVarValues: number;
    numMissingCases: number;
    isMultiValued: boolean;
  } | null;
}

interface VizPart {
  datasetId: string;
  analysisId: string;
  chart: string;
  effectSizeLabel: string;
  effectSizeThreshold: number | null;
  significanceThreshold: number | null;
  effectDirection: string | null;
  totalPoints: number;
  retainedPoints: number;
  points: {
    pointId: string;
    effectSize: number;
    pValue?: number;
    adjustedPValue?: number;
    retained: boolean;
  }[];
}

type CardComponent<P> = (props: { data: P }) => ReactElement;
type AnalysisCardModule = { DataEdaAnalysisState: CardComponent<AnalysisPart> };
type PreviewCardModule = { DataEdaSubsetPreview: CardComponent<PreviewPart> };
type VizCardModule = { DataEdaViz: CardComponent<VizPart> };

interface EdaState {
  binding: { siteId: string; datasetId: string; analysisId: string } | null;
  analysis: { analysisId: string; revision: number | null } | null;
  reset: () => void;
}

const storeModule = await loadOrSkip<{ useEdaStore: { getState: () => EdaState } }>(
  "@/state/eda",
);
const PARTS = "@/features/conversation/content/parts";
const cardModule = await loadOrSkip<AnalysisCardModule>(
  `${PARTS}/DataEdaAnalysisState`,
);
const previewModule = await loadOrSkip<PreviewCardModule>(
  `${PARTS}/DataEdaSubsetPreview`,
);
const vizModule = await loadOrSkip<VizCardModule>(`${PARTS}/DataEdaViz`);

function eda(): EdaState {
  return (
    storeModule as { useEdaStore: { getState: () => EdaState } }
  ).useEdaStore.getState();
}

/** Text with thousands separators removed, so a count assertion does not
 * depend on the locale format the renderer chooses. */
function plainText(node: HTMLElement): string {
  return node.textContent.replace(/,/g, "");
}

const ANALYSIS: AnalysisPart = {
  siteId: "plasmodb",
  datasetId: "DS_e973eadd57",
  studyId: "STUDY_e973eadd57",
  analysisId: "acc-a1",
  revision: 3,
  studyDisplayName: "Heat shock response in sensitive mutants (LRR5, DHC)",
  displayName: "Febrile samples",
  numFilters: 2,
  numComputations: 1,
  filters: [],
  filterSummaries: ["temperature_condition is febrile", "Temperature is 37 to 42"],
  entityCounts: [
    {
      entityId: "ENT_8151325d",
      entityDisplayName: "Sample",
      count: 6,
      unfilteredCount: 12,
    },
    {
      entityId: "ENT_fd574cd6",
      entityDisplayName: "pfal3D7 htseq counts",
      count: 34320,
      unfilteredCount: 68640,
    },
  ],
  canExportRows: true,
};

/** The live Species distribution: 4011 + 4130 + 268 = 8409 values over 4279 rows. */
const PREVIEW: PreviewPart = {
  datasetId: "DS_e973eadd57",
  analysisId: "acc-a1",
  entityCounts: [
    {
      entityId: "GENE_PHENOTYPE_DATA_ENTITY",
      entityDisplayName: "Gene phenotype",
      count: 4011,
      unfilteredCount: 4279,
    },
  ],
  distribution: {
    variableId: "VAR_035294d0",
    variableDisplayName: "Species",
    labels: ["P. berghei", "P. falciparum", "P. yoelii"],
    values: [4011, 4130, 268],
    subsetSize: 4279,
    numVarValues: 8409,
    numMissingCases: 0,
    isMultiValued: true,
  },
};

const VOLCANO: VizPart = {
  datasetId: "DS_e973eadd57",
  analysisId: "acc-a1",
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
    { pointId: "PF3D7_MIT04200", effectSize: -1.49447459261845, retained: false },
  ],
};

const cardsMissing = cardModule === null || storeModule === null;

describe.skipIf(cardsMissing)("the analysis-state card in the thread", () => {
  beforeEach(() => {
    eda().reset();
  });

  it("names the study and the analysis as two distinct texts", () => {
    const Card = (cardModule as AnalysisCardModule).DataEdaAnalysisState;
    render(<Card data={ANALYSIS} />);
    expect(
      screen.getByText("Heat shock response in sensitive mutants (LRR5, DHC)"),
    ).toBeInTheDocument();
    expect(screen.getByText("Febrile samples")).toBeInTheDocument();
  });

  it("renders one chip per backend filter summary, in order", () => {
    const Card = (cardModule as AnalysisCardModule).DataEdaAnalysisState;
    render(<Card data={ANALYSIS} />);
    const chips = screen.getAllByTestId(/^data-eda-filter-chip-/);
    expect(chips).toHaveLength(2);
    expect(chips[0]).toHaveTextContent("temperature_condition is febrile");
    expect(chips[1]).toHaveTextContent("Temperature is 37 to 42");
  });

  it("prints every entity count against its unfiltered total", () => {
    const Card = (cardModule as AnalysisCardModule).DataEdaAnalysisState;
    render(<Card data={ANALYSIS} />);
    const card = screen.getByTestId("data-eda-analysis-state");
    expect(card).toHaveTextContent("6 of 12 Sample");
    expect(plainText(card)).toContain("34320 of 68640 pfal3D7 htseq counts");
  });

  it("hydrates the store, which is how a chat turn moves the tab", async () => {
    const Card = (cardModule as AnalysisCardModule).DataEdaAnalysisState;
    render(<Card data={ANALYSIS} />);
    await waitFor(() => {
      expect(eda().analysis?.analysisId).toBe("acc-a1");
    });
    expect(eda().analysis?.revision).toBe(3);
    expect(eda().binding).toEqual({
      siteId: "plasmodb",
      datasetId: "DS_e973eadd57",
      analysisId: "acc-a1",
    });
  });
});

describe.skipIf(previewModule === null || storeModule === null)(
  "the subset-preview card in the thread",
  () => {
    beforeEach(() => {
      eda().reset();
    });

    it("prints the entity count line for each entity", () => {
      const Card = (previewModule as PreviewCardModule).DataEdaSubsetPreview;
      render(<Card data={PREVIEW} />);
      const card = screen.getByTestId("data-eda-subset-preview");
      expect(plainText(card)).toContain("4011 of 4279 Gene phenotype");
    });

    it("warns that a multi-valued variable outruns the subset size", () => {
      const Card = (previewModule as PreviewCardModule).DataEdaSubsetPreview;
      render(<Card data={PREVIEW} />);
      expect(screen.getByTestId("data-eda-subset-multivalued")).toHaveTextContent(
        "one record can carry several values",
      );
      expect(plainText(screen.getByTestId("data-eda-subset-coverage"))).toContain(
        "8409 of 4279 records have a value",
      );
    });
  },
);

describe.skipIf(vizModule === null || storeModule === null)(
  "the viz card in the thread",
  () => {
    beforeEach(() => {
      eda().reset();
    });

    it("draws the volcano and reports the compute's own retained count", () => {
      const Card = (vizModule as VizCardModule).DataEdaViz;
      render(<Card data={VOLCANO} />);
      expect(screen.getByTestId("eda-viz-volcano")).toHaveAttribute("role", "img");
      const line = screen.getByTestId("eda-viz-volcano-selection");
      expect(line).toHaveTextContent("1 gene selected");
      expect(plainText(line)).toContain("1543 of 5511");
    });

    it("reports the row that carries no p-value", () => {
      const Card = (vizModule as VizCardModule).DataEdaViz;
      render(<Card data={VOLCANO} />);
      expect(screen.getByTestId("eda-viz-volcano-dropped")).toHaveTextContent(
        "1 point without a p-value was not plotted",
      );
    });

    it("names a histogram as unsupported instead of drawing a wrong chart", () => {
      const Card = (vizModule as VizCardModule).DataEdaViz;
      render(<Card data={{ ...VOLCANO, chart: "histogram" }} />);
      expect(screen.getByTestId("data-eda-viz-unsupported-chart")).toHaveTextContent(
        "histogram plots are not available from this compute",
      );
      expect(screen.queryByTestId("eda-viz-volcano")).toBe(null);
    });

    it("draws a scatter with no threshold control in the thread", () => {
      const Card = (vizModule as VizCardModule).DataEdaViz;
      render(<Card data={{ ...VOLCANO, chart: "scatter" }} />);
      expect(screen.getByTestId("eda-viz-scatter")).toHaveAttribute("role", "img");
      expect(screen.queryByLabelText("Effect size threshold")).toBe(null);
    });
  },
);
