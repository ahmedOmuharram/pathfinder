// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { CombineOperator } from "@pathfinder/shared";
import { MiniVenn } from "./MiniVenn";

describe("MiniVenn", () => {
  it("renders both circles filled for UNION", () => {
    const { container } = render(<MiniVenn operator={CombineOperator.UNION} />);
    const left = container.querySelector('[data-region="left-only"]');
    const right = container.querySelector('[data-region="right-only"]');
    const lens = container.querySelector('[data-region="lens"]');
    expect(left?.getAttribute("data-active")).toBe("true");
    expect(right?.getAttribute("data-active")).toBe("true");
    expect(lens?.getAttribute("data-active")).toBe("true");
  });

  it("renders only the lens for INTERSECT", () => {
    const { container } = render(
      <MiniVenn operator={CombineOperator.INTERSECT} />,
    );
    const left = container.querySelector('[data-region="left-only"]');
    const right = container.querySelector('[data-region="right-only"]');
    const lens = container.querySelector('[data-region="lens"]');
    expect(left?.getAttribute("data-active")).toBe("false");
    expect(right?.getAttribute("data-active")).toBe("false");
    expect(lens?.getAttribute("data-active")).toBe("true");
  });

  it("renders left circle minus lens for MINUS", () => {
    const { container } = render(<MiniVenn operator={CombineOperator.MINUS} />);
    const left = container.querySelector('[data-region="left-only"]');
    const right = container.querySelector('[data-region="right-only"]');
    const lens = container.querySelector('[data-region="lens"]');
    expect(left?.getAttribute("data-active")).toBe("true");
    expect(right?.getAttribute("data-active")).toBe("false");
    expect(lens?.getAttribute("data-active")).toBe("false");
  });

  it("renders right circle minus lens for RMINUS", () => {
    const { container } = render(
      <MiniVenn operator={CombineOperator.RMINUS} />,
    );
    const left = container.querySelector('[data-region="left-only"]');
    const right = container.querySelector('[data-region="right-only"]');
    const lens = container.querySelector('[data-region="lens"]');
    expect(left?.getAttribute("data-active")).toBe("false");
    expect(right?.getAttribute("data-active")).toBe("true");
    expect(lens?.getAttribute("data-active")).toBe("false");
  });

  it("falls back to separated circles + arrow for COLOCATE", () => {
    const { container } = render(
      <MiniVenn operator={CombineOperator.COLOCATE} />,
    );
    expect(container.querySelector('[data-mode="colocate"]')).not.toBeNull();
    expect(
      container.querySelector('[data-region="colocate-arrow"]'),
    ).not.toBeNull();
  });
});
