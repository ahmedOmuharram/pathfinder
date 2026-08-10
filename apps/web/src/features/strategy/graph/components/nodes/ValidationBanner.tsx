"use client";

import type { Step } from "@pathfinder/shared";
import type { StepSnapshot } from "@/state/strategy/useStepSnapshot";

export type ValidationBannerProps = {
  step: Step;
  snapshot: StepSnapshot;
  onOpenDetails?: ((stepId: string) => void) | undefined;
};

export function ValidationBanner({
  step,
  snapshot,
  onOpenDetails,
}: ValidationBannerProps) {
  // A WDK rejection is shown even when the lifecycle machine is idle: the
  // push failed on the server, so nothing local transitions to "invalid".
  if (!snapshot.isInvalid && !snapshot.isFailed && snapshot.wdkPushError == null) {
    return null;
  }
  const message =
    snapshot.wdkPushError ??
    snapshot.validationErrors?.general?.[0] ??
    snapshot.lastError ??
    "Validation error";

  return (
    <div className="mt-1 text-center text-xs font-semibold text-destructive">
      <span data-testid="validation-message">{message}</span>
      {onOpenDetails != null && (
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onOpenDetails(step.id);
          }}
          className="ml-1 text-xs font-semibold text-destructive underline decoration-destructive/30 underline-offset-2 hover:text-destructive"
        >
          View details
        </button>
      )}
    </div>
  );
}
