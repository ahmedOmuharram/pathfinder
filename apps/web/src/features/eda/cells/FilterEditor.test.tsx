/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { EdaVariableResponse } from "@pathfinder/shared/generated/types/EdaVariableResponse";

import { FilterEditor } from "./FilterEditor";

const SPECIES: EdaVariableResponse = {
  entityId: "ENT_8151325d",
  variableId: "VAR_035294d0",
  displayName: "Species",
  variableType: "string",
  filterType: "stringSet",
  dataShape: "categorical",
  isMultiValued: true,
  vocabulary: ["P. berghei", "P. falciparum", "P. yoelii"],
  vocabularyTotal: 3,
  vocabularyNote: null,
  rangeMin: null,
  rangeMax: null,
  dateMin: null,
  dateMax: null,
  subFilterVariableIds: [],
  hideFrom: [],
};

const TEMPERATURE: EdaVariableResponse = {
  entityId: "ENT_8151325d",
  variableId: "VAR_7033e90f",
  displayName: "Temperature",
  variableType: "integer",
  filterType: "numberRange",
  dataShape: "continuous",
  isMultiValued: false,
  vocabulary: [],
  vocabularyTotal: 0,
  vocabularyNote: null,
  rangeMin: 37,
  rangeMax: 42,
  dateMin: null,
  dateMax: null,
  subFilterVariableIds: [],
  hideFrom: [],
};

const COLLECTION_DATE: EdaVariableResponse = {
  entityId: "OBI_0000659",
  variableId: "EUPATH_0043256",
  displayName: "Collection date",
  variableType: "date",
  filterType: "dateRange",
  dataShape: "continuous",
  isMultiValued: false,
  vocabulary: [],
  vocabularyTotal: 0,
  vocabularyNote: null,
  rangeMin: null,
  rangeMax: null,
  dateMin: "2017-05-05T00:00:00",
  dateMax: "2017-05-11T00:00:00",
  subFilterVariableIds: [],
  hideFrom: [],
};

const READ_COUNTS: EdaVariableResponse = {
  entityId: "ENT_fd574cd6",
  variableId: "SEQUENCE_READ_COUNT_SENSE",
  displayName: "Read count, sense",
  variableType: "integer",
  filterType: "numberSet",
  dataShape: "ordinal",
  isMultiValued: false,
  vocabulary: [],
  vocabularyTotal: 0,
  vocabularyNote: null,
  rangeMin: 0,
  rangeMax: 68640,
  dateMin: null,
  dateMax: null,
  subFilterVariableIds: [],
  hideFrom: [],
};

describe("FilterEditor stringSet", () => {
  it("offers every vocabulary value as a checkbox", () => {
    render(
      <FilterEditor
        variable={SPECIES}
        current={null}
        onApply={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getAllByRole("checkbox")).toHaveLength(3);
  });

  it("keeps Apply disabled until a value is checked", async () => {
    render(
      <FilterEditor
        variable={SPECIES}
        current={null}
        onApply={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const apply = screen.getByRole("button", { name: "Apply filter" });
    expect(apply).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: "P. falciparum" }));
    expect(apply).toBeEnabled();
  });

  it("emits a stringSet filter naming the checked values", async () => {
    const onApply = vi.fn();
    render(
      <FilterEditor
        variable={SPECIES}
        current={null}
        onApply={onApply}
        onCancel={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "P. falciparum" }));
    await userEvent.click(screen.getByRole("button", { name: "Apply filter" }));
    expect(onApply).toHaveBeenCalledWith({
      entityId: "ENT_8151325d",
      variableId: "VAR_035294d0",
      type: "stringSet",
      stringSet: ["P. falciparum"],
    });
  });

  it("keeps the vocabulary order when two values are checked out of order", async () => {
    const onApply = vi.fn();
    render(
      <FilterEditor
        variable={SPECIES}
        current={null}
        onApply={onApply}
        onCancel={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "P. yoelii" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "P. berghei" }));
    await userEvent.click(screen.getByRole("button", { name: "Apply filter" }));
    expect(onApply).toHaveBeenCalledWith({
      entityId: "ENT_8151325d",
      variableId: "VAR_035294d0",
      type: "stringSet",
      stringSet: ["P. berghei", "P. yoelii"],
    });
  });

  it("warns that per-value counts do not partition a multi-valued variable", () => {
    render(
      <FilterEditor
        variable={SPECIES}
        current={null}
        onApply={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByTestId("eda-filter-multivalued-note")).toHaveTextContent(
      "one record can carry several values",
    );
  });

  it("seeds the checkboxes from an existing filter", () => {
    render(
      <FilterEditor
        variable={SPECIES}
        current={{
          entityId: "ENT_8151325d",
          variableId: "VAR_035294d0",
          type: "stringSet",
          stringSet: ["P. yoelii"],
        }}
        onApply={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByRole("checkbox", { name: "P. yoelii" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "P. berghei" })).not.toBeChecked();
  });
});

describe("FilterEditor numberRange", () => {
  it("seeds the bounds from the variable range defaults", () => {
    render(
      <FilterEditor
        variable={TEMPERATURE}
        current={null}
        onApply={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Minimum")).toHaveValue(37);
    expect(screen.getByLabelText("Maximum")).toHaveValue(42);
  });

  it("emits numeric bounds, not strings", async () => {
    const onApply = vi.fn();
    render(
      <FilterEditor
        variable={TEMPERATURE}
        current={null}
        onApply={onApply}
        onCancel={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Apply filter" }));
    expect(onApply).toHaveBeenCalledWith({
      entityId: "ENT_8151325d",
      variableId: "VAR_7033e90f",
      type: "numberRange",
      min: 37,
      max: 42,
    });
  });

  it("refuses to apply while a bound is blank", async () => {
    render(
      <FilterEditor
        variable={TEMPERATURE}
        current={null}
        onApply={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    await userEvent.clear(screen.getByLabelText("Minimum"));
    expect(screen.getByRole("button", { name: "Apply filter" })).toBeDisabled();
  });

  it("seeds from the existing filter rather than the variable defaults", () => {
    render(
      <FilterEditor
        variable={TEMPERATURE}
        current={{
          entityId: "ENT_8151325d",
          variableId: "VAR_7033e90f",
          type: "numberRange",
          min: 38,
          max: 40,
        }}
        onApply={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Minimum")).toHaveValue(38);
    expect(screen.getByLabelText("Maximum")).toHaveValue(40);
  });
});

describe("FilterEditor dateRange", () => {
  it("appends the time part the service requires", async () => {
    const onApply = vi.fn();
    render(
      <FilterEditor
        variable={COLLECTION_DATE}
        current={null}
        onApply={onApply}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Minimum")).toHaveValue("2017-05-05");
    await userEvent.click(screen.getByRole("button", { name: "Apply filter" }));
    expect(onApply).toHaveBeenCalledWith({
      entityId: "OBI_0000659",
      variableId: "EUPATH_0043256",
      type: "dateRange",
      min: "2017-05-05T00:00:00",
      max: "2017-05-11T00:00:00",
    });
  });
});

describe("FilterEditor read-only types", () => {
  it("says where a set filter can be authored instead of offering an editor", () => {
    render(
      <FilterEditor
        variable={READ_COUNTS}
        current={null}
        onApply={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByTestId("eda-filter-read-only")).toHaveTextContent(
      "Set membership and multi-filters are available through chat.",
    );
    expect(screen.queryByRole("button", { name: "Apply filter" })).toBe(null);
  });
});

describe("FilterEditor cancel", () => {
  it("reports the dismissal without emitting a filter", async () => {
    const onApply = vi.fn();
    const onCancel = vi.fn();
    render(
      <FilterEditor
        variable={TEMPERATURE}
        current={null}
        onApply={onApply}
        onCancel={onCancel}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onApply).toHaveBeenCalledTimes(0);
  });
});
