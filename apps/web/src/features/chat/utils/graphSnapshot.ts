import type { StrategyStep, StrategyWithMeta } from "@/features/strategy/types";

export interface GraphSnapshotStepInput {
  id: string;
  kind?: string;
  displayName?: string;
  searchName?: string;
  operator?: string;
  parameters?: Record<string, unknown>;
  inputStepIds?: string[];
  primaryInputStepId?: string;
  secondaryInputStepId?: string;
  recordType?: string;
}

export interface GraphSnapshotInput {
  graphId?: string;
  graphName?: string;
  recordType?: string | null;
  name?: string;
  description?: string | null;
  rootStepId?: string | null;
  steps?: GraphSnapshotStepInput[];
}

const isUrlLike = (value: string | null | undefined) =>
  typeof value === "string" &&
  (value.startsWith("http://") || value.startsWith("https://"));

const normalizeName = (value: string | null | undefined) =>
  typeof value === "string" ? value.trim().toLowerCase() : "";

const isFallbackDisplayName = (
  name: string | null | undefined,
  step: {
    kind?: string;
    searchName?: string;
    operator?: string;
  },
) => {
  if (!name) return true;
  if (isUrlLike(name)) return true;
  const normalized = normalizeName(name);
  const candidates = new Set<string>([
    normalizeName(step.searchName),
    normalizeName(step.kind),
  ]);
  if (step.operator) {
    const op = normalizeName(step.operator);
    candidates.add(op);
    candidates.add(`${op} combine`);
  }
  return candidates.has(normalized);
};

const toStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  return value.filter((v): v is string => typeof v === "string");
};

export function buildStrategyFromGraphSnapshot(args: {
  snapshotId: string;
  siteId: string;
  graphSnapshot: GraphSnapshotInput;
  stepsById: Record<string, StrategyStep | undefined>;
  existingStrategy?: StrategyWithMeta | null;
}): StrategyWithMeta {
  const {
    snapshotId,
    siteId,
    graphSnapshot,
    stepsById,
    existingStrategy = null,
  } = args;
  const hasStepsField = "steps" in (graphSnapshot as Record<string, unknown>);
  const snapshotSteps = Array.isArray(graphSnapshot.steps) ? graphSnapshot.steps : null;

  const steps: StrategyStep[] = snapshotSteps
    ? snapshotSteps
        .filter(
          (step): step is GraphSnapshotStepInput =>
            !!step && typeof step.id === "string",
        )
        .map((step) => {
          const existing = stepsById[step.id];
          const incomingName = step.displayName || step.kind;
          const existingName = existing?.displayName;
          const keepExisting =
            !!existingName &&
            (!incomingName ||
              !isFallbackDisplayName(existingName, existing) ||
              isFallbackDisplayName(incomingName, step));
          const resolvedName =
            (keepExisting ? existingName : incomingName) ||
            step.searchName ||
            step.kind ||
            step.id;
          const resolvedRecordType = step.recordType ?? existing?.recordType;
          const inputs = toStringArray(step.inputStepIds);
          const primaryInputStepId = step.primaryInputStepId ?? inputs[0] ?? undefined;
          const secondaryInputStepId =
            step.secondaryInputStepId ?? inputs[1] ?? undefined;

          return {
            id: step.id,
            kind: (step.kind ?? "search") as StrategyStep["kind"],
            displayName: resolvedName,
            recordType: resolvedRecordType ?? undefined,
            searchName: step.searchName,
            operator: (step.operator as StrategyStep["operator"]) ?? undefined,
            parameters: step.parameters,
            primaryInputStepId,
            secondaryInputStepId,
          };
        })
    : // If the snapshot omitted `steps` entirely, treat this as a metadata-only update
      // and keep the current graph steps instead of wiping the UI.
      hasStepsField
      ? []
      : Object.values(stepsById).filter((s): s is StrategyStep => !!s);

  const now = new Date().toISOString();
  return {
    id: snapshotId,
    name:
      graphSnapshot.name ||
      graphSnapshot.graphName ||
      existingStrategy?.name ||
      "Draft Strategy",
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
    description:
      graphSnapshot.description !== undefined
        ? (graphSnapshot.description ?? undefined)
        : existingStrategy?.description,
    createdAt: existingStrategy?.createdAt || now,
    updatedAt: now,
  };
}
