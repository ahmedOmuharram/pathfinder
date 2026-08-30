/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from "vitest";

import { RECORDED_CHUNKS, loadOrSkip, renderTurn } from "./support";

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

const devModeModule = await loadOrSkip<Record<string, unknown>>(
  "@/features/conversation/thread/useThreadDevMode",
);

describe.skipIf(devModeModule === null)("the thread's dev mode", () => {
  it("reveals one raw region per row when showRawToolCalls is on", () => {
    const view = renderTurn(RECORDED_CHUNKS, { showRaw: true, showUsage: true });
    expect(view.getAllByTestId("trace-row")).toHaveLength(7);
    expect(view.getAllByTestId("trace-row-raw")).toHaveLength(7);
    const text = view.container.textContent;
    expect(text).toContain("wdkStepId");
    expect(text).toContain("DS_e973eadd57");
  });

  it("leaves no raw region and no JSON when the flag goes back off", () => {
    const first = renderTurn(RECORDED_CHUNKS, { showRaw: true, showUsage: true });
    expect(first.getAllByTestId("trace-row-raw")).toHaveLength(7);
    first.unmount();

    const view = renderTurn(RECORDED_CHUNKS, { showRaw: false, showUsage: true });
    expect(view.queryAllByTestId("trace-row-raw")).toHaveLength(0);
    const text = view.container.textContent;
    expect(text).toContain("I looked at the heat shock study");
    expect(text).not.toContain("datasetId");
    expect(text).not.toContain("wdkStepId");
    expect(text).not.toContain("{\n");
  });

  it("hides the model badge and every group usage when showTokenUsage is off", () => {
    const view = renderTurn(RECORDED_CHUNKS, { showRaw: false, showUsage: false });
    expect(view.queryByTestId("model-badge")).toBe(null);
    expect(view.queryAllByTestId("trace-group-usage")).toHaveLength(0);
    expect(view.getAllByTestId("trace-row")).toHaveLength(7);
  });

  it("shows both again on the default, which is showTokenUsage on", () => {
    const view = renderTurn(RECORDED_CHUNKS, { showRaw: false, showUsage: true });
    expect(view.getByTestId("model-badge")).toHaveTextContent("41.8K, $0.01");
    expect(view.getAllByTestId("trace-group-usage")).toHaveLength(1);
  });
});
