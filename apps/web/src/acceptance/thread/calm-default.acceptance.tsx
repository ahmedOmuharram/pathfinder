/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from "vitest";
import { within } from "@testing-library/react";

import {
  ENRICHMENT_TASK_CHUNKS,
  RECORDED_CHUNKS,
  SETTLED_CHUNKS,
  loadOrSkip,
  renderTurn,
} from "./support";

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

const traceModule = await loadOrSkip<Record<string, unknown>>(
  "@/lib/components/thread/Trace",
);

const CALM = { showRaw: false, showUsage: true };

/** The seven rows of the recorded turn, each with the label
 * `humanizeToolName` returns and the summary its own tool wrote. */
const ROWS: readonly (readonly [string, string | null])[] = [
  ["Search eda studies", "3 studies matched heat shock"],
  ["Open eda analysis", "Opened Febrile samples on DS_e973eadd57"],
  ["Search catalog", "12 searches"],
  ["Set criterion", "c1 set to GenesByText"],
  ["Preview eda subset", "6 of 12 Sample"],
  ["Run control tests", "8 of 10 positive controls recovered"],
  ["Optimize parameters", null],
];

function trimmed(node: HTMLElement): string {
  return node.textContent.trim();
}

function at(nodes: readonly HTMLElement[], index: number, what: string): HTMLElement {
  const node = nodes[index];
  if (node === undefined) throw new Error(`${what} ${index} is missing`);
  return node;
}

describe.skipIf(traceModule === null)("the thread's calm default", () => {
  it("draws one trace for the turn's one run of tool calls", () => {
    const view = renderTurn(RECORDED_CHUNKS, CALM);
    expect(view.getAllByTestId("turn-trace")).toHaveLength(1);
  });

  it("reads Waiting for you while a call still waits on the user", () => {
    const view = renderTurn(RECORDED_CHUNKS, CALM);
    expect(trimmed(view.getByTestId("turn-trace-summary"))).toBe("Waiting for you");
  });

  it("reads 7 steps once every call has settled", () => {
    const view = renderTurn(SETTLED_CHUNKS, CALM);
    expect(trimmed(view.getByTestId("turn-trace-summary"))).toBe("7 steps");
  });

  it("gives each of the seven calls one row, named and summarised", () => {
    const view = renderTurn(RECORDED_CHUNKS, CALM);
    const rows = view.getAllByTestId("trace-row");
    expect(rows).toHaveLength(7);
    ROWS.forEach(([label, summary], index) => {
      const row = at(rows, index, "trace row");
      expect(row).toHaveTextContent(label);
      if (summary === null) {
        expect(within(row).queryByTestId("trace-row-summary")).toBe(null);
        return;
      }
      expect(trimmed(within(row).getByTestId("trace-row-summary"))).toBe(summary);
    });
  });

  it("labels the three groups Lead, Frame and Lead", () => {
    const view = renderTurn(RECORDED_CHUNKS, CALM);
    const labels = view.getAllByTestId("trace-group-label").map(trimmed);
    expect(labels).toEqual(["Lead", "Frame", "Lead"]);
  });

  it("prints the frame group's usage as an ASCII comma pair", () => {
    const view = renderTurn(RECORDED_CHUNKS, CALM);
    const frame = view
      .getAllByTestId("trace-group")
      .find(
        (group) => trimmed(within(group).getByTestId("trace-group-label")) === "Frame",
      );
    if (frame === undefined) throw new Error("no group is labelled Frame");
    expect(trimmed(within(frame).getByTestId("trace-group-usage"))).toBe(
      "12.3K, $0.004",
    );
  });

  it("puts no tool JSON anywhere in the document", () => {
    const view = renderTurn(RECORDED_CHUNKS, CALM);
    const text = view.container.textContent;
    expect(text).toContain("I looked at the heat shock study");
    expect(text).not.toContain("datasetId");
    expect(text).not.toContain("wdkStepId");
    expect(text).not.toContain("distributionVariableId");
    expect(text).not.toContain("{\n");
  });

  it("renders the durable job as one task row that reads Completed", () => {
    const view = renderTurn(RECORDED_CHUNKS, CALM);
    const rows = view.getAllByTestId("task-row");
    expect(rows).toHaveLength(1);
    const row = at(rows, 0, "task row");
    expect(row).toHaveTextContent("Run control tests");
    expect(trimmed(within(row).getByTestId("task-row-status"))).toBe("Completed");
    expect(within(row).getByTestId("progress-bar-fill")).toBeInTheDocument();
  });

  it("keeps the task progress inside the task row and nowhere else", () => {
    const view = renderTurn(RECORDED_CHUNKS, CALM);
    const bars = view.getAllByTestId("data-task-progress");
    expect(bars).toHaveLength(1);
    expect(view.getByTestId("task-row").contains(at(bars, 0, "progress bar"))).toBe(
      true,
    );
  });

  it("names the enrichment task by the tool name the wire carries", () => {
    const view = renderTurn(ENRICHMENT_TASK_CHUNKS, CALM);
    expect(view.getByTestId("task-row")).toHaveTextContent("Gene set enrichment");
  });

  it("asks for the sweep's approval in one card that names the tool", () => {
    const view = renderTurn(RECORDED_CHUNKS, CALM);
    expect(view.getAllByTestId("approval-card")).toHaveLength(1);
    expect(trimmed(view.getByTestId("approval-card-title"))).toBe(
      "Optimize parameters needs your approval before it runs.",
    );
    expect(view.getByTestId("tool-approval-approve")).toBeInTheDocument();
    expect(view.getByTestId("tool-approval-deny")).toBeInTheDocument();
  });

  it("prints the lead's own tokens and cost on the model badge", () => {
    const view = renderTurn(RECORDED_CHUNKS, CALM);
    expect(view.getByTestId("model-badge")).toHaveTextContent("41.8K, $0.01");
  });
});
