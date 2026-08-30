/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/lib/components/charts/echartsRegistry", () => ({
  initChart: () => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: () => false,
  }),
}));

import { useEdaStore } from "@/state/eda";
import { DataEdaViz } from "./DataEdaViz";
import {
  EDA_ANALYSIS_STATE_FIXTURE,
  EDA_SCATTER_VIZ_FIXTURE,
  EDA_VOLCANO_VIZ_FIXTURE,
} from "./edaPartFixtures";

beforeEach(() => {
  useEdaStore.getState().reset();
  useEdaStore.getState().applyAnalysisState(EDA_ANALYSIS_STATE_FIXTURE);
});

describe("DataEdaViz volcano", () => {
  it("names the plot in the figure title and draws the volcano", () => {
    render(<DataEdaViz data={EDA_VOLCANO_VIZ_FIXTURE} />);
    const title = screen.getByText("log2(Fold Change)");
    expect(title.tagName).toBe("FIGCAPTION");
    expect(screen.getByTestId("eda-viz-volcano")).toHaveAttribute("role", "img");
  });

  it("captions the figure with the compute's retained count", () => {
    render(
      <DataEdaViz
        data={{ ...EDA_VOLCANO_VIZ_FIXTURE, totalPoints: 5511, retainedPoints: 1543 }}
      />,
    );
    expect(screen.getByTestId("figure-caption").textContent).toBe(
      "1,543 of 5,511 genes retained",
    );
  });

  it("separates itself with a hairline, never with a card", () => {
    render(<DataEdaViz data={EDA_VOLCANO_VIZ_FIXTURE} />);
    expect(screen.getByTestId("figure").className.split(/\s+/)).toEqual([
      "my-6",
      "border-t",
      "border-border/60",
      "pt-4",
    ]);
    expect(screen.getByTestId("data-eda-viz").className).not.toMatch(
      /\bborder\b|\brounded-md\b|\bbg-card\b/,
    );
  });

  it("reports the client selection and the compute's own retained count", () => {
    render(<DataEdaViz data={EDA_VOLCANO_VIZ_FIXTURE} />);
    const line = screen.getByTestId("eda-viz-volcano-selection");
    expect(line).toHaveTextContent("1 gene selected");
    expect(line).toHaveTextContent("1 of 3 retained by the compute");
  });

  it("lists the selected gene beside the plot", () => {
    render(<DataEdaViz data={EDA_VOLCANO_VIZ_FIXTURE} />);
    expect(screen.getByTestId("eda-viz-volcano-genes")).toHaveTextContent(
      "PF3D7_0100200",
    );
  });

  it("caps the collapsed height and expands on request", async () => {
    render(<DataEdaViz data={EDA_VOLCANO_VIZ_FIXTURE} />);
    expect(screen.getByTestId("eda-viz-volcano")).toHaveStyle({ height: "220px" });
    await userEvent.click(screen.getByRole("button", { name: "Expand plot" }));
    expect(screen.getByTestId("eda-viz-volcano")).toHaveStyle({ height: "480px" });
    expect(screen.getByRole("button", { name: "Collapse plot" })).toBeInTheDocument();
  });

  it("hydrates the store so the tab shows the same plot", async () => {
    render(<DataEdaViz data={EDA_VOLCANO_VIZ_FIXTURE} />);
    await waitFor(() => {
      expect(useEdaStore.getState().viz["volcano"]?.retainedPoints).toBe(1);
    });
  });

  it("reports the point it could not plot", () => {
    render(<DataEdaViz data={EDA_VOLCANO_VIZ_FIXTURE} />);
    expect(screen.getByTestId("eda-viz-volcano-dropped")).toHaveTextContent(
      "1 point without a p-value was not plotted",
    );
  });

  it("uses the thresholds the tab set, so both surfaces agree", () => {
    useEdaStore.getState().setVolcanoThresholds({
      effectSizeThreshold: 4,
      significanceThreshold: 0.05,
      direction: "upAndDown",
    });
    render(<DataEdaViz data={EDA_VOLCANO_VIZ_FIXTURE} />);
    expect(screen.getByTestId("eda-viz-volcano-selection")).toHaveTextContent(
      "0 genes selected",
    );
    expect(screen.queryByTestId("eda-viz-volcano-genes")).toBe(null);
  });
});

describe("DataEdaViz other charts", () => {
  it("draws the scatter and names both axes", () => {
    render(<DataEdaViz data={EDA_SCATTER_VIZ_FIXTURE} />);
    expect(screen.getByTestId("eda-viz-scatter")).toHaveAttribute(
      "aria-label",
      "Scatter plot of -log10(p-value) against log2(Fold Change), 2 points",
    );
  });

  it("counts the scatter points beside the plot", () => {
    render(<DataEdaViz data={EDA_SCATTER_VIZ_FIXTURE} />);
    expect(screen.getByTestId("eda-viz-scatter-count")).toHaveTextContent(
      "2 of 3 points plotted",
    );
  });

  it("drops a scatter point at p = 0 as well as one with no p-value", () => {
    render(
      <DataEdaViz
        data={{
          ...EDA_SCATTER_VIZ_FIXTURE,
          totalPoints: 4,
          points: [
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
              effectSize: 1.1,
              pValue: 0,
              adjustedPValue: 0,
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
        }}
      />,
    );
    expect(screen.getByTestId("eda-viz-scatter-count")).toHaveTextContent(
      "2 of 4 points plotted",
    );
    expect(screen.getByTestId("eda-viz-scatter")).toHaveAttribute(
      "aria-label",
      "Scatter plot of -log10(p-value) against log2(Fold Change), 2 points",
    );
    expect(screen.queryByTestId("eda-viz-scatter-dropped")).toBe(null);
  });

  it("says a bar plot cannot be drawn from a point cloud", () => {
    render(<DataEdaViz data={{ ...EDA_VOLCANO_VIZ_FIXTURE, chart: "bar" }} />);
    expect(screen.getByTestId("data-eda-viz-unsupported-chart")).toHaveTextContent(
      "bar plots are not available from this compute",
    );
  });

  it("says the same for a histogram and a boxplot", () => {
    const { unmount } = render(
      <DataEdaViz data={{ ...EDA_VOLCANO_VIZ_FIXTURE, chart: "histogram" }} />,
    );
    expect(screen.getByTestId("data-eda-viz-unsupported-chart")).toHaveTextContent(
      "histogram plots are not available from this compute",
    );
    unmount();
    render(<DataEdaViz data={{ ...EDA_VOLCANO_VIZ_FIXTURE, chart: "boxplot" }} />);
    expect(screen.getByTestId("data-eda-viz-unsupported-chart")).toHaveTextContent(
      "boxplot plots are not available from this compute",
    );
  });

  it("says so when the payload carries no points at all", () => {
    render(<DataEdaViz data={{ ...EDA_VOLCANO_VIZ_FIXTURE, points: [] }} />);
    expect(screen.getByTestId("data-eda-viz-empty")).toHaveTextContent(
      "This compute returned no points",
    );
    expect(screen.queryByTestId("eda-viz-volcano")).toBe(null);
  });
});
