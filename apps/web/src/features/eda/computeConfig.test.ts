import { describe, expect, it } from "vitest";
import type { EdaVariableResponse } from "@pathfinder/shared/generated/types/EdaVariableResponse";

import {
  buildDifferentialExpressionConfig,
  comparatorVariables,
  computeConfigProblem,
  DifferentialExpressionConfigError,
  geneIdentifierVariable,
  isComputeConfigComplete,
  valueVariables,
} from "./computeConfig";

const draft = {
  identifierEntityId: "ENT_fd574cd6",
  identifierVariableId: "VEUPATHDB_GENE_ID",
  valueVariableId: "SEQUENCE_READ_COUNT_SENSE",
  comparatorEntityId: "ENT_8151325d",
  comparatorVariableId: "VAR_081ab087",
  groupA: ["normal"],
  groupB: ["febrile"],
  method: "DESeq" as const,
};

/** Every field the route now answers with, so a fixture is a real payload. */
function variable(overrides: Partial<EdaVariableResponse>): EdaVariableResponse {
  return {
    entityId: "ENT_8151325d",
    variableId: "VAR_081ab087",
    displayName: "temperature_condition",
    variableType: "string",
    filterType: "stringSet",
    dataShape: "categorical",
    isMultiValued: false,
    vocabulary: [],
    vocabularyTotal: 0,
    vocabularyNote: null,
    rangeMin: null,
    rangeMax: null,
    dateMin: null,
    dateMax: null,
    subFilterVariableIds: [],
    hideFrom: [],
    ...overrides,
  };
}

const GENE_ID = variable({
  entityId: "ENT_fd574cd6",
  variableId: "VEUPATHDB_GENE_ID",
  displayName: "Gene ID",
});

const READ_COUNT = variable({
  entityId: "ENT_fd574cd6",
  variableId: "SEQUENCE_READ_COUNT_SENSE",
  displayName: "Read count, sense",
  variableType: "integer",
  filterType: "numberRange",
  dataShape: "continuous",
  rangeMin: 0,
  rangeMax: 168342,
});

const TPM = variable({
  entityId: "ENT_fd574cd6",
  variableId: "TPM",
  displayName: "TPM",
  variableType: "number",
  filterType: "numberRange",
  dataShape: "continuous",
  rangeMin: 0,
  rangeMax: 4210.5,
});

const TEMPERATURE = variable({
  vocabulary: ["febrile", "normal"],
  vocabularyTotal: 2,
});

const SPECIES = variable({
  variableId: "OBI_0001909",
  displayName: "species",
  dataShape: "binary",
  vocabulary: ["Aedes aegypti", "Aedes albopictus"],
  vocabularyTotal: 2,
});

const COLLECTION_DATE = variable({
  variableId: "VAR_date",
  displayName: "collection date",
  variableType: "date",
  filterType: "dateRange",
  dataShape: "continuous",
  dateMin: "2026-01-01T00:00:00",
  dateMax: "2026-06-30T00:00:00",
});

const ALL = [GENE_ID, READ_COUNT, TPM, TEMPERATURE, SPECIES, COLLECTION_DATE];

describe("buildDifferentialExpressionConfig", () => {
  it("builds the recorded live request config", () => {
    expect(buildDifferentialExpressionConfig(draft)).toEqual({
      identifierVariable: {
        entityId: "ENT_fd574cd6",
        variableId: "VEUPATHDB_GENE_ID",
      },
      valueVariable: {
        entityId: "ENT_fd574cd6",
        variableId: "SEQUENCE_READ_COUNT_SENSE",
      },
      comparator: {
        variable: { entityId: "ENT_8151325d", variableId: "VAR_081ab087" },
        groupA: [{ label: "normal" }],
        groupB: [{ label: "febrile" }],
      },
      differentialExpressionMethod: "DESeq",
      pValueFloor: "1e-200",
    });
  });

  it("puts the value variable on the identifier variable's entity", () => {
    const config = buildDifferentialExpressionConfig(draft);
    expect(config.valueVariable.entityId).toBe(config.identifierVariable.entityId);
  });

  it("accepts limma as the other wire method", () => {
    expect(
      buildDifferentialExpressionConfig({ ...draft, method: "limma" })
        .differentialExpressionMethod,
    ).toBe("limma");
  });

  it("keeps the p-value floor a string", () => {
    expect(buildDifferentialExpressionConfig(draft).pValueFloor).toBe("1e-200");
  });

  it("throws when a group shares a label with the other group", () => {
    expect(() =>
      buildDifferentialExpressionConfig({ ...draft, groupB: ["normal"] }),
    ).toThrow(DifferentialExpressionConfigError);
  });

  it("names the shared label in the error message", () => {
    expect(() =>
      buildDifferentialExpressionConfig({ ...draft, groupB: ["normal"] }),
    ).toThrow("Group A and group B use the same label: normal");
  });

  it("throws when a group is empty", () => {
    expect(() => buildDifferentialExpressionConfig({ ...draft, groupB: [] })).toThrow(
      DifferentialExpressionConfigError,
    );
  });

  it("throws when no comparator variable is chosen", () => {
    expect(() =>
      buildDifferentialExpressionConfig({ ...draft, comparatorVariableId: "" }),
    ).toThrow("The comparator variable is not chosen");
  });

  it("throws when no value variable is chosen", () => {
    expect(() =>
      buildDifferentialExpressionConfig({ ...draft, valueVariableId: "" }),
    ).toThrow("The value variable is not chosen");
  });
});

describe("isComputeConfigComplete", () => {
  it("is true for the recorded draft", () => {
    expect(isComputeConfigComplete(draft)).toBe(true);
  });

  it("is false while no comparator variable is chosen", () => {
    expect(isComputeConfigComplete({ ...draft, comparatorVariableId: "" })).toBe(false);
  });

  it("is false while either group is empty", () => {
    expect(isComputeConfigComplete({ ...draft, groupA: [] })).toBe(false);
  });

  it("is false while the two groups share a label", () => {
    expect(isComputeConfigComplete({ ...draft, groupB: ["normal"] })).toBe(false);
  });

  it("is false while no value variable is chosen", () => {
    expect(isComputeConfigComplete({ ...draft, valueVariableId: "" })).toBe(false);
  });
});

describe("computeConfigProblem", () => {
  it("names the shared label", () => {
    expect(computeConfigProblem({ ...draft, groupB: ["normal"] })).toBe(
      "Group A and group B use the same label: normal",
    );
  });

  it("is silent while the draft is merely unfinished", () => {
    expect(computeConfigProblem({ ...draft, groupB: [] })).toBe(null);
  });

  it("is silent for a complete draft", () => {
    expect(computeConfigProblem(draft)).toBe(null);
  });
});

describe("geneIdentifierVariable", () => {
  it("is the VEUPATHDB_GENE_ID variable", () => {
    expect(geneIdentifierVariable(ALL)).toEqual({
      entityId: "ENT_fd574cd6",
      variableId: "VEUPATHDB_GENE_ID",
    });
  });

  it("is null when the study declares no gene id variable", () => {
    expect(geneIdentifierVariable([TEMPERATURE, READ_COUNT])).toBe(null);
  });
});

describe("valueVariables", () => {
  it("is the numeric variables on the identifier's entity", () => {
    expect(valueVariables(ALL, "ENT_fd574cd6").map((v) => v.variableId)).toEqual([
      "SEQUENCE_READ_COUNT_SENSE",
      "TPM",
    ]);
  });

  it("drops a numeric variable on another entity", () => {
    expect(valueVariables(ALL, "ENT_8151325d")).toEqual([]);
  });
});

describe("comparatorVariables", () => {
  it("keeps every vocabulary-bearing variable, on any entity", () => {
    expect(comparatorVariables(ALL).map((v) => v.variableId)).toEqual([
      "VAR_081ab087",
      "OBI_0001909",
    ]);
  });

  it("drops a continuous variable, which carries no groups", () => {
    expect(comparatorVariables([COLLECTION_DATE, READ_COUNT])).toEqual([]);
  });

  it("drops a categorical variable whose vocabulary is empty", () => {
    expect(comparatorVariables([{ ...TEMPERATURE, vocabulary: [] }])).toEqual([]);
  });
});
