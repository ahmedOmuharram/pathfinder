/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/components/charts/echartsRegistry", () => ({
  initChart: () => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: () => false,
  }),
}));

import { useEdaStore } from "@/state/eda";
import { DataEdaSubsetPreview } from "./DataEdaSubsetPreview";
import {
  EDA_ANALYSIS_STATE_FIXTURE,
  EDA_SUBSET_PREVIEW_FIXTURE,
} from "./edaPartFixtures";

const DISTRIBUTION = EDA_SUBSET_PREVIEW_FIXTURE.distribution;
if (DISTRIBUTION === null) throw new Error("the fixture carries a distribution");

beforeEach(() => {
  useEdaStore.getState().reset();
  useEdaStore.getState().applyAnalysisState(EDA_ANALYSIS_STATE_FIXTURE);
});

describe("DataEdaSubsetPreview", () => {
  it("prints each entity count against its unfiltered total", () => {
    render(<DataEdaSubsetPreview data={EDA_SUBSET_PREVIEW_FIXTURE} />);
    expect(screen.getByTestId("data-eda-subset-preview")).toHaveTextContent(
      "6 of 12 Sample",
    );
  });

  it("draws the distribution as a mini histogram named after the variable", () => {
    render(<DataEdaSubsetPreview data={EDA_SUBSET_PREVIEW_FIXTURE} />);
    expect(screen.getByTestId("data-eda-subset-histogram")).toHaveAttribute(
      "aria-label",
      "Temperature distribution over the subset",
    );
  });

  it("prints every bin label against its value", () => {
    render(<DataEdaSubsetPreview data={EDA_SUBSET_PREVIEW_FIXTURE} />);
    const bins = screen.getAllByTestId(/^data-eda-subset-bin-/);
    expect(bins).toHaveLength(2);
    expect(bins[0]).toHaveTextContent("[37, 38) 6");
    expect(bins[1]).toHaveTextContent("[41, 42] 6");
  });

  it("reports how many records carry a value", () => {
    render(<DataEdaSubsetPreview data={EDA_SUBSET_PREVIEW_FIXTURE} />);
    expect(screen.getByTestId("data-eda-subset-coverage")).toHaveTextContent(
      "6 of 6 records have a value",
    );
  });

  it("warns when the variable is multi-valued, because the bars do not add up", () => {
    render(
      <DataEdaSubsetPreview
        data={{
          ...EDA_SUBSET_PREVIEW_FIXTURE,
          distribution: { ...DISTRIBUTION, isMultiValued: true, numVarValues: 9 },
        }}
      />,
    );
    expect(screen.getByTestId("data-eda-subset-multivalued")).toHaveTextContent(
      "one record can carry several values",
    );
    expect(screen.getByTestId("data-eda-subset-coverage")).toHaveTextContent(
      "9 of 6 records have a value",
    );
  });

  it("omits the warning when the variable is single-valued", () => {
    render(<DataEdaSubsetPreview data={EDA_SUBSET_PREVIEW_FIXTURE} />);
    expect(screen.queryByTestId("data-eda-subset-multivalued")).toBe(null);
  });

  it("omits the histogram when the part carries no distribution", () => {
    render(
      <DataEdaSubsetPreview
        data={{ ...EDA_SUBSET_PREVIEW_FIXTURE, distribution: null }}
      />,
    );
    expect(screen.queryByTestId("data-eda-subset-histogram")).toBe(null);
    expect(screen.getByTestId("data-eda-subset-preview")).toHaveTextContent(
      "6 of 12 Sample",
    );
  });

  it("prints the note the backend attached to the distribution", () => {
    render(
      <DataEdaSubsetPreview
        data={{
          ...EDA_SUBSET_PREVIEW_FIXTURE,
          distributionNote: "Temperature has 40 bins, the first 10 are shown",
        }}
      />,
    );
    expect(screen.getByTestId("data-eda-subset-note")).toHaveTextContent(
      "Temperature has 40 bins, the first 10 are shown",
    );
  });

  it("hydrates the store", async () => {
    render(<DataEdaSubsetPreview data={EDA_SUBSET_PREVIEW_FIXTURE} />);
    await waitFor(() => {
      expect(useEdaStore.getState().subsetPreview?.entityCounts[0]?.count).toBe(6);
    });
  });
});
