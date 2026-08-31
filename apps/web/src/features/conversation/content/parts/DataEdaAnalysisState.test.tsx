/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { pushMock, route } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  route: { pathname: "/plasmodb/conversation/conv-1" },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => route.pathname,
}));

import { edaTabUrl } from "@/lib/routes";
import { useEdaStore } from "@/state/eda";
import { DataEdaAnalysisState } from "./DataEdaAnalysisState";
import { EDA_ANALYSIS_STATE_FIXTURE } from "./edaPartFixtures";

beforeEach(() => {
  useEdaStore.getState().reset();
  pushMock.mockClear();
  route.pathname = "/plasmodb/conversation/conv-1";
});

describe("DataEdaAnalysisState", () => {
  it("titles the figure with the study and lists each filtered entity count", () => {
    render(<DataEdaAnalysisState data={EDA_ANALYSIS_STATE_FIXTURE} />);
    expect(screen.getByTestId("figure")).toHaveTextContent(
      "Heat shock response in sensitive mutants (LRR5, DHC)",
    );
    const card = screen.getByTestId("data-eda-analysis-state");
    expect(card).toHaveTextContent("Sample");
    expect(card).toHaveTextContent("34,320");
  });

  it("captions the figure with every entity count, joined and separated", () => {
    render(<DataEdaAnalysisState data={EDA_ANALYSIS_STATE_FIXTURE} />);
    expect(screen.getByTestId("figure-caption")).toHaveTextContent(
      "6 of 12 Sample, 34,320 of 68,640 pfal3D7 htseq counts",
    );
  });

  it("falls back to the dataset id when the study has no display name", () => {
    render(
      <DataEdaAnalysisState
        data={{ ...EDA_ANALYSIS_STATE_FIXTURE, studyDisplayName: "" }}
      />,
    );
    expect(screen.getByText("DS_e973eadd57")).toBeInTheDocument();
  });

  it("separates itself with a hairline, never with a card", () => {
    render(<DataEdaAnalysisState data={EDA_ANALYSIS_STATE_FIXTURE} />);
    const figure = screen.getByTestId("figure");
    expect(figure.className.split(/\s+/)).toEqual([
      "my-6",
      "border-t",
      "border-border/60",
      "pt-4",
    ]);
    expect(screen.getByTestId("data-eda-analysis-state").className).not.toMatch(
      /\bborder\b|\brounded-md\b|\bbg-card\b/,
    );
  });

  it("hydrates the store so the tab reflects a chat-driven change", async () => {
    render(<DataEdaAnalysisState data={EDA_ANALYSIS_STATE_FIXTURE} />);
    await waitFor(() => {
      expect(useEdaStore.getState().analysis?.analysisId).toBe("a-1");
    });
    const state = useEdaStore.getState();
    expect(state.analysis?.revision).toBe(3);
    expect(state.analysis?.filters).toHaveLength(2);
    expect(state.binding).toEqual({
      siteId: "plasmodb",
      datasetId: "DS_e973eadd57",
      analysisId: "a-1",
    });
  });

  it("hydrates once for one payload, however many times it re-renders", async () => {
    const { rerender } = render(
      <DataEdaAnalysisState data={EDA_ANALYSIS_STATE_FIXTURE} />,
    );
    await waitFor(() => {
      expect(useEdaStore.getState().analysis?.revision).toBe(3);
    });
    useEdaStore.getState().setLocalFilters([]);
    rerender(<DataEdaAnalysisState data={EDA_ANALYSIS_STATE_FIXTURE} />);
    expect(useEdaStore.getState().localFilters).toEqual([]);
  });
});

describe("DataEdaAnalysisState chips and navigation", () => {
  it("names the study and the analysis separately", () => {
    render(<DataEdaAnalysisState data={EDA_ANALYSIS_STATE_FIXTURE} />);
    expect(
      screen.getByText("Heat shock response in sensitive mutants (LRR5, DHC)"),
    ).toBeInTheDocument();
    expect(screen.getByText("Febrile samples")).toBeInTheDocument();
  });

  it("renders one chip per backend filter summary, in order", () => {
    render(<DataEdaAnalysisState data={EDA_ANALYSIS_STATE_FIXTURE} />);
    const chips = screen.getAllByTestId(/^data-eda-filter-chip-/);
    expect(chips).toHaveLength(2);
    expect(chips[0]).toHaveTextContent("temperature_condition is febrile");
    expect(chips[1]).toHaveTextContent("Temperature is 37 to 42");
  });

  it("keys chips by position, so two identical summaries both render", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    const summaries = [
      "temperature_condition is febrile",
      "temperature_condition is febrile",
    ];
    const { rerender } = render(
      <DataEdaAnalysisState
        data={{ ...EDA_ANALYSIS_STATE_FIXTURE, filterSummaries: summaries }}
      />,
    );
    rerender(
      <DataEdaAnalysisState
        data={{
          ...EDA_ANALYSIS_STATE_FIXTURE,
          filterSummaries: [...summaries, "Temperature is 37 to 42"],
        }}
      />,
    );
    expect(screen.getAllByTestId(/^data-eda-filter-chip-/)).toHaveLength(3);
    expect(screen.getByTestId("data-eda-filter-chip-0")).toHaveTextContent(
      "temperature_condition is febrile",
    );
    expect(screen.getByTestId("data-eda-filter-chip-1")).toHaveTextContent(
      "temperature_condition is febrile",
    );
    expect(consoleError).not.toHaveBeenCalled();
    consoleError.mockRestore();
  });

  it("prints each entity count against its unfiltered total", () => {
    render(<DataEdaAnalysisState data={EDA_ANALYSIS_STATE_FIXTURE} />);
    const card = screen.getByTestId("data-eda-analysis-state");
    expect(card).toHaveTextContent("6 of 12 Sample");
    expect(card).toHaveTextContent("34,320 of 68,640 pfal3D7 htseq counts");
  });

  it("says the subset is unfiltered when there are no summaries", () => {
    render(
      <DataEdaAnalysisState
        data={{
          ...EDA_ANALYSIS_STATE_FIXTURE,
          numFilters: 0,
          filters: [],
          filterSummaries: [],
        }}
      />,
    );
    expect(screen.getByTestId("data-eda-analysis-state")).toHaveTextContent(
      "No filters yet",
    );
    expect(screen.queryByTestId("data-eda-filter-overflow")).toBe(null);
  });

  it("says how many filters the backend counted when it rendered fewer summaries", () => {
    render(
      <DataEdaAnalysisState data={{ ...EDA_ANALYSIS_STATE_FIXTURE, numFilters: 5 }} />,
    );
    expect(screen.getByTestId("data-eda-filter-overflow")).toHaveTextContent(
      "3 more filters",
    );
  });

  it("opens the EDA tab for the conversation in the path", async () => {
    render(<DataEdaAnalysisState data={EDA_ANALYSIS_STATE_FIXTURE} />);
    await userEvent.click(screen.getByRole("button", { name: "Open study" }));
    expect(pushMock).toHaveBeenCalledWith(edaTabUrl("plasmodb", "conv-1"));
  });
});

describe("DataEdaAnalysisState off a conversation route", () => {
  afterEach(() => {
    route.pathname = "/plasmodb/conversation/conv-1";
  });

  it("has no open action when the path names no conversation", () => {
    route.pathname = "/plasmodb/workbench";
    render(<DataEdaAnalysisState data={EDA_ANALYSIS_STATE_FIXTURE} />);
    expect(screen.queryByRole("button", { name: "Open study" })).toBe(null);
    expect(screen.getByTestId("data-eda-analysis-state")).toHaveTextContent(
      "Febrile samples",
    );
  });
});
