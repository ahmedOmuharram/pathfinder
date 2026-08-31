// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

vi.mock("@tanstack/react-query-devtools", () => ({
  ReactQueryDevtools: ({ buttonPosition }: { buttonPosition: string }) => (
    <div data-testid="devtools-toggle" data-button-position={buttonPosition} />
  ),
}));

import { QueryProvider } from "./QueryProvider";

describe("QueryProvider", () => {
  afterEach(cleanup);

  it("puts the devtools toggle off the left edge, which the nav rail owns", () => {
    render(<QueryProvider>{null}</QueryProvider>);

    expect(screen.getByTestId("devtools-toggle")).toHaveAttribute(
      "data-button-position",
      "bottom-right",
    );
  });
});
