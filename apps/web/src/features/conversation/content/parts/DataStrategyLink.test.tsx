/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataStrategyLink } from "./DataStrategyLink";

describe("DataStrategyLink", () => {
  it("renders link with title", () => {
    render(
      <DataStrategyLink
        data={{
          strategyId: "s1",
          url: "https://plasmodb.org/plasmo/app/workspace/strategies/s1",
          title: "My Strategy",
        }}
      />,
    );
    expect(screen.getByTestId("data-strategy-link")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "My Strategy" });
    expect(link).toHaveAttribute(
      "href",
      "https://plasmodb.org/plasmo/app/workspace/strategies/s1",
    );
  });

  it("renders fallback text when no title", () => {
    render(
      <DataStrategyLink data={{ strategyId: "s2", url: "https://plasmodb.org/s2" }} />,
    );
    expect(screen.getByText("Strategy s2")).toBeInTheDocument();
  });
});
