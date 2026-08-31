/**
 * @vitest-environment jsdom
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cloneElement,
  createContext,
  useContext,
  type ReactElement,
  type ReactNode,
} from "react";
import { cleanup, render, screen, within } from "@testing-library/react";
import type { EnrichmentTerm } from "@pathfinder/shared";
import { EnrichmentDotPlot } from "./EnrichmentDotPlot";
import { pvalGradient } from "./enrichment-utils";

interface DotDatum {
  name: string;
  foldEnrichment: number | null;
  geneCount: number;
  pValue: number | null;
  dotRadius: number;
}

interface ShapeProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  payload?: DotDatum;
}

interface TipProps {
  active?: boolean;
  payload?: { payload: DotDatum }[];
}

// The mock feeds every datum through the real DotShape and DotPlotTooltip,
// which is where an unbounded fold enrichment has to be handled.
vi.mock("recharts", () => {
  const DataContext = createContext<DotDatum[]>([]);

  return {
    ResponsiveContainer: ({ children }: { children: ReactNode }) => (
      <div>{children}</div>
    ),
    BarChart: ({ data, children }: { data: DotDatum[]; children: ReactNode }) => (
      <DataContext.Provider value={data}>{children}</DataContext.Provider>
    ),
    YAxis: () => {
      const data = useContext(DataContext);
      return (
        <ul data-testid="axis">
          {data.map((d) => (
            <li key={d.name}>{d.name}</li>
          ))}
        </ul>
      );
    },
    Bar: ({ shape }: { shape: ReactElement<ShapeProps> }) => {
      const data = useContext(DataContext);
      return (
        <svg>
          {data.map((d) => (
            <g key={d.name} data-testid={`mark-${d.name}`}>
              {cloneElement(shape, { payload: d, x: 0, y: 0, width: 12, height: 20 })}
            </g>
          ))}
        </svg>
      );
    },
    Tooltip: ({ content }: { content: ReactElement<TipProps> }) => {
      const data = useContext(DataContext);
      return (
        <div>
          {data.map((d) => (
            <div key={d.name} data-testid={`tip-${d.name}`}>
              {cloneElement(content, { active: true, payload: [{ payload: d }] })}
            </div>
          ))}
        </div>
      );
    },
    XAxis: () => null,
    CartesianGrid: () => null,
  };
});

function term(overrides: Partial<EnrichmentTerm> = {}): EnrichmentTerm {
  return {
    termId: "GO:0004672",
    termName: "protein kinase activity",
    geneCount: 3,
    backgroundCount: 120,
    foldEnrichment: 3.48,
    oddsRatio: 4.12,
    pValue: 0.0001,
    fdr: 0.002,
    bonferroni: 0.005,
    genes: [],
    ...overrides,
  };
}

const UNBOUNDED = term({
  termId: "GO:0006260",
  termName: "dna replication",
  geneCount: 5,
  foldEnrichment: null,
  pValue: 0.002,
});

describe("EnrichmentDotPlot", () => {
  afterEach(cleanup);

  it("keeps the axis label of an unbounded term but draws no dot for it", () => {
    render(<EnrichmentDotPlot terms={[term(), UNBOUNDED]} />);

    expect(screen.getByTestId("axis")).toHaveTextContent("dna replication");
    expect(
      screen.getByTestId("mark-dna replication").querySelectorAll("circle"),
    ).toHaveLength(0);
  });

  it("draws a dot for a term whose fold enrichment is a number", () => {
    render(<EnrichmentDotPlot terms={[term(), UNBOUNDED]} />);

    const axis = within(screen.getByTestId("axis"));
    expect(axis.getByText("protein kinase activity")).toBeTruthy();
    const dot = screen
      .getByTestId("mark-protein kinase activity")
      .querySelector("circle");
    expect(dot).not.toBeNull();
    // 3 of the 5 genes of the largest term: 4 + 0.6 * (14 - 4).
    expect(dot?.getAttribute("r")).toBe("10");
  });

  it("ramps the legend swatch from the chart tokens", () => {
    const root = document.documentElement;
    root.style.setProperty("--chart-1", "215 75% 45%");
    root.style.setProperty("--chart-4", "355 70% 45%");
    try {
      render(<EnrichmentDotPlot terms={[term()]} />);
      const swatch = screen.getByText("-log10(p)").previousElementSibling;
      expect(swatch).toHaveStyle({ background: pvalGradient() });
      const light = swatch?.getAttribute("style");
      cleanup();

      root.style.setProperty("--chart-1", "210 90% 70%");
      root.style.setProperty("--chart-4", "355 80% 70%");
      render(<EnrichmentDotPlot terms={[term()]} />);
      const darkSwatch = screen.getByText("-log10(p)").previousElementSibling;
      expect(darkSwatch).toHaveStyle({ background: pvalGradient() });
      expect(darkSwatch?.getAttribute("style")).not.toBe(light);
    } finally {
      root.removeAttribute("style");
    }
  });

  it("reports the unbounded term as Inf and the finite one by its value", () => {
    render(<EnrichmentDotPlot terms={[term(), UNBOUNDED]} />);

    const unbounded = screen.getByTestId("tip-dna replication");
    expect(unbounded).toHaveTextContent("Fold: Inf");
    expect(unbounded).toHaveTextContent("Genes: 5");
    expect(unbounded).toHaveTextContent("p: 2.00e-3");

    const finite = screen.getByTestId("tip-protein kinase activity");
    expect(finite).toHaveTextContent("Fold: 3.48");
    expect(finite).toHaveTextContent("p: 1.00e-4");
  });
});
