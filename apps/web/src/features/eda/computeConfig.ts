import type { EdaDifferentialExpressionConfig } from "@pathfinder/shared/generated/types/EdaDifferentialExpressionConfig";
import type { EdaVariableResponse } from "@pathfinder/shared/generated/types/EdaVariableResponse";
import type { EdaVariableSpec } from "@pathfinder/shared/generated/types/EdaVariableSpec";

const P_VALUE_FLOOR = "1e-200";
export const GENE_ID_VARIABLE = "VEUPATHDB_GENE_ID";

const NUMERIC_TYPES = ["integer", "number"];
const GROUPED_SHAPES = ["categorical", "ordinal", "binary"];

export type DifferentialExpressionMethod = "DESeq" | "limma";

export interface ComputeConfigDraft {
  identifierEntityId: string;
  identifierVariableId: string;
  valueVariableId: string;
  comparatorEntityId: string;
  comparatorVariableId: string;
  groupA: readonly string[];
  groupB: readonly string[];
  method: DifferentialExpressionMethod;
}

export class DifferentialExpressionConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DifferentialExpressionConfigError";
  }
}

function sharedLabel(draft: ComputeConfigDraft): string | null {
  return draft.groupA.find((label) => draft.groupB.includes(label)) ?? null;
}

/** The rule a complete draft still breaks, or null while it breaks none. */
export function computeConfigProblem(draft: ComputeConfigDraft): string | null {
  const shared = sharedLabel(draft);
  return shared === null ? null : `Group A and group B use the same label: ${shared}`;
}

export function isComputeConfigComplete(draft: ComputeConfigDraft): boolean {
  return (
    draft.identifierEntityId !== "" &&
    draft.identifierVariableId !== "" &&
    draft.valueVariableId !== "" &&
    draft.comparatorEntityId !== "" &&
    draft.comparatorVariableId !== "" &&
    draft.groupA.length > 0 &&
    draft.groupB.length > 0 &&
    sharedLabel(draft) === null
  );
}

export function buildDifferentialExpressionConfig(
  draft: ComputeConfigDraft,
): EdaDifferentialExpressionConfig {
  if (draft.identifierVariableId === "") {
    throw new DifferentialExpressionConfigError(
      `The study declares no ${GENE_ID_VARIABLE} variable`,
    );
  }
  if (draft.valueVariableId === "") {
    throw new DifferentialExpressionConfigError("The value variable is not chosen");
  }
  if (draft.comparatorVariableId === "") {
    throw new DifferentialExpressionConfigError(
      "The comparator variable is not chosen",
    );
  }
  if (draft.groupA.length === 0 || draft.groupB.length === 0) {
    throw new DifferentialExpressionConfigError("Both groups need at least one label");
  }
  const problem = computeConfigProblem(draft);
  if (problem !== null) throw new DifferentialExpressionConfigError(problem);

  return {
    identifierVariable: {
      entityId: draft.identifierEntityId,
      variableId: draft.identifierVariableId,
    },
    valueVariable: {
      entityId: draft.identifierEntityId,
      variableId: draft.valueVariableId,
    },
    comparator: {
      variable: {
        entityId: draft.comparatorEntityId,
        variableId: draft.comparatorVariableId,
      },
      groupA: draft.groupA.map((label) => ({ label })),
      groupB: draft.groupB.map((label) => ({ label })),
    },
    differentialExpressionMethod: draft.method,
    pValueFloor: P_VALUE_FLOOR,
  };
}

/** The gene identifier the export needs. A study declares at most one. */
export function geneIdentifierVariable(
  variables: readonly EdaVariableResponse[],
): EdaVariableSpec | null {
  const found = variables.find((variable) => variable.variableId === GENE_ID_VARIABLE);
  return found === undefined
    ? null
    : { entityId: found.entityId, variableId: found.variableId };
}

/** The plugin reads the value variable from the identifier's own entity. */
export function valueVariables(
  variables: readonly EdaVariableResponse[],
  entityId: string,
): EdaVariableResponse[] {
  return variables.filter(
    (variable) =>
      variable.entityId === entityId && NUMERIC_TYPES.includes(variable.variableType),
  );
}

/** A comparator needs labelled groups, so it needs a vocabulary. */
export function comparatorVariables(
  variables: readonly EdaVariableResponse[],
): EdaVariableResponse[] {
  return variables.filter(
    (variable) =>
      variable.dataShape != null &&
      GROUPED_SHAPES.includes(variable.dataShape) &&
      variable.vocabulary.length > 0,
  );
}
