// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { NumberRangeParam } from "./NumberRangeParam";
import type { ParamSpec } from "@pathfinder/shared";
import { WidgetTestForm, getInputByLabel } from "./testUtils";

afterEach(cleanup);

function makeSpec(overrides: Partial<ParamSpec> = {}): ParamSpec {
  return {
    name: "r",
    type: "number-range",
    displayName: "R",
    displayType: "",
    allowEmptyValue: true,
    isVisible: true,
    isNumber: true,
    countOnlyLeaves: false,
    ...overrides,
  } as ParamSpec;
}

describe("NumberRangeParam", () => {
  it("renders two number inputs for min and max", () => {
    render(
      <WidgetTestForm name="r" defaultValue="">
        {(field) => <NumberRangeParam spec={makeSpec()} name="r" options={[]} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    const inputs = screen.getAllByRole("spinbutton");
    expect(inputs.length).toBe(2);
  });

  it("encodes range as 'min-max' on change", () => {
    render(
      <WidgetTestForm name="r" defaultValue="">
        {(field) => <NumberRangeParam spec={makeSpec()} name="r" options={[]} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    const minInput = getInputByLabel("r min");
    const maxInput = getInputByLabel("r max");
    fireEvent.change(minInput, { target: { value: "5" } });
    fireEvent.change(maxInput, { target: { value: "10" } });
    expect(minInput.value).toBe("5");
    expect(maxInput.value).toBe("10");
  });

  it("decodes existing 'min-max' value", () => {
    render(
      <WidgetTestForm name="r" defaultValue="3-7">
        {(field) => <NumberRangeParam spec={makeSpec()} name="r" options={[]} vocabTree={null} field={field} />}
      </WidgetTestForm>,
    );
    const minInput = getInputByLabel("r min");
    const maxInput = getInputByLabel("r max");
    expect(minInput.value).toBe("3");
    expect(maxInput.value).toBe("7");
  });
});
