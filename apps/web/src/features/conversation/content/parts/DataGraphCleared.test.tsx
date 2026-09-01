/**
 * @vitest-environment jsdom
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { DataGraphCleared } from "./DataGraphCleared";

describe("DataGraphCleared", () => {
  it("renders one caption line naming the reason", () => {
    render(<DataGraphCleared data={{ reason: "the user asked for a fresh start" }} />);
    expect(screen.getByTestId("figure-caption").textContent).toBe(
      "Strategy cleared - the user asked for a fresh start",
    );
  });

  it("says only that the strategy was cleared when no reason came over the wire", () => {
    render(<DataGraphCleared data={{ reason: null }} />);
    expect(screen.getByTestId("figure-caption").textContent).toBe("Strategy cleared");
  });

  it("carries its own testid and draws no chrome at all", () => {
    const { container } = render(<DataGraphCleared data={{ reason: "replaced" }} />);
    const line = screen.getByTestId("data-graph-cleared");
    const figure = screen.getByTestId("figure");
    expect(line).toHaveTextContent("Strategy cleared - replaced");
    expect(figure.contains(line)).toBe(true);
    expect(figure.className).toBe("");
    expect(container.querySelectorAll("figcaption")).toHaveLength(0);
  });
});
