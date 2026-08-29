/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";

const { chartDouble, initChart } = vi.hoisted(() => {
  const chart = {
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: vi.fn(() => false),
  };
  return { chartDouble: chart, initChart: vi.fn(() => chart) };
});

vi.mock("./echartsRegistry", () => ({ initChart }));

import { EChart } from "./EChart";

const observed: Element[] = [];
class ObserverDouble {
  constructor(private callback: () => void) {}
  observe(target: Element) {
    observed.push(target);
    this.callback();
  }
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  initChart.mockClear();
  chartDouble.setOption.mockClear();
  chartDouble.resize.mockClear();
  chartDouble.dispose.mockClear();
  observed.length = 0;
  vi.stubGlobal("ResizeObserver", ObserverDouble);
});

const flush = () => new Promise<void>((resolve) => queueMicrotask(resolve));

describe("EChart", () => {
  it("renders an accessible sized container", () => {
    const { getByTestId } = render(
      <EChart
        option={{ series: [] }}
        height={240}
        ariaLabel="Volcano plot"
        testId="chart-under-test"
      />,
    );
    const node = getByTestId("chart-under-test");
    expect(node).toHaveAttribute("role", "img");
    expect(node).toHaveAttribute("aria-label", "Volcano plot");
    expect(node).toHaveStyle({ height: "240px" });
  });

  it("initialises exactly one instance and applies the option once", async () => {
    render(
      <EChart
        option={{ series: [] }}
        height={240}
        ariaLabel="Volcano plot"
        testId="chart-under-test"
      />,
    );
    await flush();
    expect(initChart).toHaveBeenCalledTimes(1);
    expect(chartDouble.setOption).toHaveBeenCalledTimes(1);
  });

  it("observes its own node and resizes the instance", async () => {
    const { getByTestId } = render(
      <EChart
        option={{ series: [] }}
        height={240}
        ariaLabel="Volcano plot"
        testId="chart-under-test"
      />,
    );
    await flush();
    expect(observed).toEqual([getByTestId("chart-under-test")]);
    expect(chartDouble.resize).toHaveBeenCalledTimes(1);
  });

  it("re-applies the option when a new option arrives, without re-initialising", async () => {
    const { rerender } = render(
      <EChart
        option={{ series: [] }}
        height={240}
        ariaLabel="Volcano plot"
        testId="chart-under-test"
      />,
    );
    await flush();
    rerender(
      <EChart
        option={{ series: [{ type: "scatter", data: [] }] }}
        height={240}
        ariaLabel="Volcano plot"
        testId="chart-under-test"
      />,
    );
    await flush();
    expect(initChart).toHaveBeenCalledTimes(1);
    expect(chartDouble.setOption).toHaveBeenCalledTimes(2);
  });

  it("disposes the instance on unmount", async () => {
    const { unmount } = render(
      <EChart
        option={{ series: [] }}
        height={240}
        ariaLabel="Volcano plot"
        testId="chart-under-test"
      />,
    );
    await flush();
    unmount();
    expect(chartDouble.dispose).toHaveBeenCalledTimes(1);
  });
});
