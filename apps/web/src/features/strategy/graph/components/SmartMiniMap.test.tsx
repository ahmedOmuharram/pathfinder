// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

vi.mock("@xyflow/react", async () => {
  const React = await import("react");
  return {
    ReactFlowProvider: ({ children }: { children: ReactNode }) =>
      React.createElement("div", null, children),
    MiniMap: () => React.createElement("div", { "data-testid": "minimap-stub" }),
    useStore: () => "0|0|1",
  };
});

vi.mock("@/features/strategy/graph/hooks/useCanvasIdle", () => ({
  useCanvasIdle: () => false,
}));

import { SmartMiniMap } from "./SmartMiniMap";

describe("SmartMiniMap", () => {
  afterEach(() => cleanup());

  it("returns null when nodeCount <= 8", () => {
    const { container } = render(<SmartMiniMap nodeCount={8} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders MiniMap when nodeCount > 8", () => {
    render(<SmartMiniMap nodeCount={9} />);
    expect(screen.getByTestId("smart-mini-map")).toBeTruthy();
    expect(screen.getByTestId("minimap-stub")).toBeTruthy();
  });
});
