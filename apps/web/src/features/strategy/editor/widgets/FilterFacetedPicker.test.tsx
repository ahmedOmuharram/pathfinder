// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FilterFacetedPicker } from "./FilterFacetedPicker";
import { EMPTY_FILTER_VALUE } from "./filterParamLogic";

describe("FilterFacetedPicker", () => {
  it("reports an unusable ontology through the warning token", () => {
    render(
      <FilterFacetedPicker
        ontology={{ not: "an array" }}
        value={EMPTY_FILTER_VALUE}
        onChange={() => {}}
      />,
    );
    const notice = screen.getByText(/unexpected shape/);
    expect(notice).toHaveClass("text-warning");
    expect(notice.className).not.toContain("amber");
  });
});
