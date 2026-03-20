import type { Step, Strategy } from "@pathfinder/shared";
import { DEFAULT_STREAM_NAME } from "@pathfinder/shared";
import { isFallbackDisplayName } from "@/lib/strategyGraph";
import type {
  GraphSnapshotInput,
  GraphSnapshotStepInput,
} from "@/lib/strategyGraph/types";

export type { GraphSnapshotInput };

const toStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  return value.filter((v): v is string => typeof v === "string");
};

export function buildStrategyFromGraphSnapshot(args: {
  snapshotId: string;
  siteId: string;
  graphSnapshot: GraphSnapshotInput;
  stepsById: Record<string, Step | undefined>;
  existingStrategy?: Strategy | null;
}): Strategy {
  const {
    snapshotId,
    siteId,
    graphSnapshot,
    stepsById,
    existingStrategy = null,
  } = args;
  const hasStepsField = "steps" in graphSnapshot;
  const snapshotSteps = Array.isArray(graphSnapshot.steps) ? graphSnapshot.steps : null;

  const steps: Step[] = snapshotSteps
    ? snapshotSteps
        .filter(
          (step): step is GraphSnapshotStepInput =>
            step != null && typeof step.id === "string",
        )
        .map((step) => {
          const existing = stepsById[step.id];
          const incomingName =
            (step.displayName != null && step.displayName !== ""
              ? step.displayName
              : null) ?? step.kind;
          const existingName = existing?.displayName;
          const keepExisting =
            existing != null &&
            existingName != null &&
            existingName !== "" &&
            (incomingName == null ||
              incomingName === "" ||
              !isFallbackDisplayName(existingName, existing) ||
              isFallbackDisplayName(incomingName, step));
          const resolvedName =
            (keepExisting ? existingName : incomingName) ??
            step.searchName ??
            step.kind ??
            step.id;
          const resolvedRecordType = step.recordType ?? existing?.recordType;
          const inputs = toStringArray(step.inputStepIds);
          const primaryInputStepId = step.primaryInputStepId ?? inputs[0] ?? null;
          const secondaryInputStepId = step.secondaryInputStepId ?? inputs[1] ?? null;

          return {
            id: step.id,
            kind: step.kind ?? "search",
            displayName: resolvedName,
            ...(resolvedRecordType != null ? { recordType: resolvedRecordType } : {}),
            ...(step.searchName != null ? { searchName: step.searchName } : {}),
            ...(step.operator != null ? { operator: step.operator } : {}),
            ...(step.parameters != null
              ? { parameters: step.parameters as Record<string, unknown> }
              : {}),
            ...(primaryInputStepId != null
              ? { primaryInputStepId: primaryInputStepId }
              : {}),
            ...(secondaryInputStepId != null
              ? { secondaryInputStepId: secondaryInputStepId }
              : {}),
          } satisfies Step;
        })
    : // If the snapshot omitted `steps` entirely, treat this as a metadata-only update
      // and keep the current graph steps instead of wiping the UI.
      hasStepsField
      ? []
      : Object.values(stepsById).filter((s): s is Step => !!s);

  const now = new Date().toISOString();
  const resolvedDescription =
    graphSnapshot.description !== undefined
      ? graphSnapshot.description
      : existingStrategy?.description;
  return {
    id: snapshotId,
    name:
      graphSnapshot.name ??
      graphSnapshot.graphName ??
      existingStrategy?.name ??
      DEFAULT_STREAM_NAME,
    siteId,
    recordType:
      graphSnapshot.recordType !== undefined
        ? (graphSnapshot.recordType ?? null)
        : (existingStrategy?.recordType ?? null),
    steps,
    rootStepId:
      graphSnapshot.rootStepId !== undefined
        ? (graphSnapshot.rootStepId ?? null)
        : (existingStrategy?.rootStepId ?? null),
    ...(resolvedDescription != null ? { description: resolvedDescription } : {}),
    isSaved: existingStrategy?.isSaved ?? false,
    createdAt: existingStrategy?.createdAt ?? now,
    updatedAt: now,
  };
}
