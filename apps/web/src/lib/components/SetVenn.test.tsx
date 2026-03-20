// @vitest-environment jsdom
import { afterEach, describe, it, expect, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { SetVenn } from "./SetVenn";

// Mock reaviz — D3/SVG doesn't work in jsdom
vi.mock("reaviz", () => ({
  VennDiagram: ({
    data,
    type,
  }: {
    data: { key: string[]; data: number }[];
    type: string;
  }) => (
    <div data-testid="reaviz-venn" data-type={type} data-count={data.length}>
      {data.map((d: { key: string[]; data: number }) => (
        <span key={d.key.join(",")} data-testid={`venn-datum-${d.key.join(",")}`}>
          {d.data}
        </span>
      ))}
    </div>
  ),
  VennSeries: () => <div />,
  VennArc: () => <div />,
  VennLabel: () => <div />,
  ChartTooltip: () => <div />,
}));

afterEach(cleanup);

describe("SetVenn", () => {
  const twoSets = [
    { key: "Set A", geneIds: ["g1", "g2", "g3"] },
    { key: "Set B", geneIds: ["g2", "g3", "g4", "g5"] },
  ];

  it("renders reaviz VennDiagram with euler type", () => {
    render(<SetVenn sets={twoSets} />);
    const venn = screen.getByTestId("reaviz-venn");
    expect(venn.dataset["type"]).toBe("euler");
  });

  it("passes correct data count for 2 sets (3 entries)", () => {
    render(<SetVenn sets={twoSets} />);
    const venn = screen.getByTestId("reaviz-venn");
    expect(venn.dataset["count"]).toBe("3");
  });

  it("passes log-scaled data values (not raw counts) to reaviz", () => {
    render(<SetVenn sets={twoSets} />);
    // Raw: A=3, B=4, A∩B=2. Log-scaled: log(4)≈1.39, log(5)≈1.61, log(3)≈1.10
    const aVal = Number(screen.getByTestId("venn-datum-Set A").textContent);
    const bVal = Number(screen.getByTestId("venn-datum-Set B").textContent);
    const abVal = Number(screen.getByTestId("venn-datum-Set A,Set B").textContent);
    expect(aVal).toBeCloseTo(Math.log(4), 5);
    expect(bVal).toBeCloseTo(Math.log(5), 5);
    expect(abVal).toBeCloseTo(Math.log(3), 5);
    // Ordering preserved
    expect(bVal).toBeGreaterThan(aVal);
    expect(aVal).toBeGreaterThan(abVal);
  });

  it("renders 3-set data with 7 entries", () => {
    const threeSets = [
      { key: "X", geneIds: ["g1", "g2"] },
      { key: "Y", geneIds: ["g2", "g3"] },
      { key: "Z", geneIds: ["g3", "g4"] },
    ];
    render(<SetVenn sets={threeSets} />);
    const venn = screen.getByTestId("reaviz-venn");
    expect(venn.dataset["count"]).toBe("7");
  });

  it("renders instruction text when onRegionClick provided", () => {
    render(<SetVenn sets={twoSets} onRegionClick={vi.fn()} />);
    expect(screen.getByText("Click a region to create a gene set")).toBeTruthy();
  });

  it("does not render instruction text when no onRegionClick", () => {
    render(<SetVenn sets={twoSets} />);
    expect(screen.queryByText("Click a region to create a gene set")).toBeNull();
  });
});
