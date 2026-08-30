/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from "vitest";
import { within } from "@testing-library/react";

import { RECORDED_CHUNKS, loadOrSkip, precedes, renderTurn } from "./support";

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn(), message: vi.fn() },
  Toaster: () => null,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/plasmodb/conversation/conv-acceptance",
}));

vi.mock("@/lib/components/charts/echartsRegistry", () => ({
  initChart: () => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: () => false,
  }),
}));

const figureModule = await loadOrSkip<Record<string, unknown>>(
  "@/lib/components/thread/Figure",
);

const CALM = { showRaw: false, showUsage: true };

/** The three figures of the recorded turn, in emission order: the part each
 * one draws, and the caption that carries its numbers. */
const FIGURES: readonly (readonly [string, string])[] = [
  ["data-eda-analysis-state", "6 of 12 Sample, 34,320 of 68,640 pfal3D7 htseq counts"],
  ["data-eda-subset-preview", "6 of 12 Sample, 6 values"],
  ["data-eda-viz", "1,543 of 5,511 genes retained"],
];

/** A figure is a hairline and space, never a card. */
const CARD_CLASSES = ["border", "rounded-lg", "rounded-md", "shadow-card"];

function trimmed(node: HTMLElement): string {
  return node.textContent.trim();
}

function at(nodes: readonly HTMLElement[], index: number, what: string): HTMLElement {
  const node = nodes[index];
  if (node === undefined) throw new Error(`${what} ${index} is missing`);
  return node;
}

function classes(node: HTMLElement): string[] {
  return node.className.split(/\s+/).filter((token) => token !== "");
}

describe.skipIf(figureModule === null)("the thread's figures", () => {
  it("draws three figures, all after the trace they came from", () => {
    const view = renderTurn(RECORDED_CHUNKS, CALM);
    const figures = view.getAllByTestId("figure");
    expect(figures).toHaveLength(3);
    const trace = view.getByTestId("turn-trace");
    expect(figures.map((figure) => precedes(trace, figure))).toEqual([
      true,
      true,
      true,
    ]);
  });

  it("keeps each science part inside its own figure, in emission order", () => {
    const view = renderTurn(RECORDED_CHUNKS, CALM);
    const figures = view.getAllByTestId("figure");
    FIGURES.forEach(([testId], index) => {
      const figure = at(figures, index, "figure");
      expect(within(figure).getByTestId(testId)).toBeInTheDocument();
    });
  });

  it("captions each figure with its own numbers", () => {
    const view = renderTurn(RECORDED_CHUNKS, CALM);
    const captions = view.getAllByTestId("figure-caption").map(trimmed);
    expect(captions).toEqual(FIGURES.map(([, caption]) => caption));
  });

  it("keeps the volcano an image with its own testid", () => {
    const view = renderTurn(RECORDED_CHUNKS, CALM);
    expect(view.getByTestId("eda-viz-volcano")).toHaveAttribute("role", "img");
  });

  it("gives no figure a card border, and every figure a hairline", () => {
    const view = renderTurn(RECORDED_CHUNKS, CALM);
    const figures = view.getAllByTestId("figure");
    expect(figures).toHaveLength(3);
    for (const figure of figures) {
      const tokens = classes(figure);
      expect(tokens.filter((token) => CARD_CLASSES.includes(token))).toEqual([]);
      expect(tokens).toContain("border-t");
    }
  });

  it("keeps the filter chip and the coverage line the frozen EDA suite pins", () => {
    const view = renderTurn(RECORDED_CHUNKS, CALM);
    expect(view.getByTestId("data-eda-filter-chip-0")).toHaveTextContent(
      "temperature_condition is febrile",
    );
    expect(view.getByTestId("data-eda-subset-coverage")).toHaveTextContent(
      "6 of 6 records have a value",
    );
  });
});
