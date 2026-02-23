import type { StrategyStep, StrategyWithMeta } from "@/features/strategy/types";
import { validateSearchParams } from "@/lib/api/client";
import { toUserMessage } from "@/lib/api/errors";
import { formatSearchValidationResponse } from "./format";
import { getRootSteps, validateStrategySteps } from "@/lib/strategyGraph";
import { normalizeRecordType } from "@/features/strategy/recordType";
import { inferStepKind } from "@/lib/strategyGraph";

export async function validateStepsForSave(args: {
  siteId: string;
  steps: StrategyStep[];
  strategy: StrategyWithMeta | null;
}): Promise<{
  errorsByStepId: Record<string, string | undefined>;
  hasErrors: boolean;
}> {
  const { siteId, steps, strategy } = args;
  const errorsByStepId: Record<string, string | undefined> = {};

  if (steps.length === 0) return { errorsByStepId, hasErrors: false };

  const structuralErrors = validateStrategySteps(steps);
  for (const issue of structuralErrors) {
    if (issue.stepId) {
      errorsByStepId[issue.stepId] = `Cannot be saved: ${issue.message}`;
      continue;
    }

    // Some structural errors are graph-level (no specific stepId). Assign them to
    // relevant steps so the UI can surface the issue and saving is blocked.
    if (issue.code === "MULTIPLE_ROOTS") {
      const roots = getRootSteps(steps);
      for (const root of roots) {
        errorsByStepId[root.id] = `Cannot be saved: ${issue.message}`;
      }
      continue;
    }
    if (issue.code === "ORPHAN_STEP") {
      for (const step of steps) {
        errorsByStepId[step.id] = `Cannot be saved: ${issue.message}`;
      }
      continue;
    }
  }

  await Promise.all(
    steps.map(async (step) => {
      if (inferStepKind(step) !== "search") {
        // Preserve structural errors already set (MISSING_INPUT, MISSING_OPERATOR, etc.).
        // Only clear when there is no structural issue.
        if (!errorsByStepId[step.id]) {
          errorsByStepId[step.id] = undefined;
        }
        return;
      }

      const rawRecordType = step.recordType || strategy?.recordType || undefined;
      const recordType = normalizeRecordType(rawRecordType);
      const searchName = step.searchName;

      if (!recordType || !searchName) {
        errorsByStepId[step.id] =
          "Cannot be saved: search name or record type missing.";
        return;
      }

      try {
        const response = await validateSearchParams(
          siteId,
          recordType,
          searchName,
          step.parameters || {},
        );
        const formatted = formatSearchValidationResponse(response);
        if (!errorsByStepId[step.id]) {
          errorsByStepId[step.id] = formatted.message || undefined;
        }
      } catch (err) {
        if (!errorsByStepId[step.id]) {
          errorsByStepId[step.id] =
            `Cannot be saved: ${toUserMessage(err, "validation failed.")}`;
        }
      }
    }),
  );

  const hasErrors = Object.values(errorsByStepId).some(Boolean);
  return { errorsByStepId, hasErrors };
}
