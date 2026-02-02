import type { StrategyStep, StrategyWithMeta } from "@/types/strategy";
import { validateSearchParams } from "@/lib/api/client";
import { toUserMessage } from "@/lib/api/errors";
import { formatSearchValidationResponse } from "./format";
import { validateStrategySteps } from "@/features/strategy/domain/graph";
import { toApiRecordType } from "@/features/strategy/recordType";

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
    if (!issue.stepId) continue;
    errorsByStepId[issue.stepId] = `Cannot be saved: ${issue.message}`;
  }

  await Promise.all(
    steps.map(async (step) => {
      if (step.type !== "search") {
        errorsByStepId[step.id] = undefined;
        return;
      }

      const rawRecordType = step.recordType || strategy?.recordType || undefined;
      // Preserve existing behavior: some sites use transcript for gene-level endpoints.
      const recordType = toApiRecordType(rawRecordType);
      const searchName = step.searchName;

      if (!recordType || !searchName) {
        errorsByStepId[step.id] = "Cannot be saved: search name or record type missing.";
        return;
      }

      try {
        const response = await validateSearchParams(
          siteId,
          recordType,
          searchName,
          step.parameters || {}
        );
        const formatted = formatSearchValidationResponse(response);
        if (!errorsByStepId[step.id]) {
          errorsByStepId[step.id] = formatted.message || undefined;
        }
      } catch (err) {
        if (!errorsByStepId[step.id]) {
          errorsByStepId[step.id] = `Cannot be saved: ${toUserMessage(err, "validation failed.")}`;
        }
      }
    })
  );

  const hasErrors = Object.values(errorsByStepId).some(Boolean);
  return { errorsByStepId, hasErrors };
}

