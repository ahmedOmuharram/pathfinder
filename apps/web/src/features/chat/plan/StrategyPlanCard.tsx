"use client";

/**
 * Thin viewer for a `PlanArtifact` data part emitted by the planner.
 *
 * Renders the proposed plan as an ordered list (search name + per-step
 * rationale) plus the overall plan rationale. When the matching
 * `tool-propose_plan` part is awaiting approval, the caller may pass that
 * tool-call part via `pendingApprovalPart` to render the modal `ApprovalDialog`
 * inline beneath the plan summary — this is the prominent-approval pathway
 * referenced in the chat-overhaul plan (Task 5g).
 *
 * Field names use the wire-aliased camelCase keys (`planId`, `searchName`,
 * `rationale`) that match the backend `CamelModel` serialization for the
 * `PlanArtifact` schema.
 */

import type { PlanArtifact } from "@pathfinder/shared";

import { ApprovalDialog } from "@/features/chat/approval/ApprovalDialog";

type PendingApprovalPart = Parameters<typeof ApprovalDialog>[0]["part"];

interface StrategyPlanCardProps {
  plan: PlanArtifact;
  pendingApprovalPart?: PendingApprovalPart;
}

export function StrategyPlanCard({
  plan,
  pendingApprovalPart,
}: StrategyPlanCardProps) {
  return (
    <div className="strategy-plan-card" data-plan-id={plan.planId}>
      <h3 className="strategy-plan-card__title">Proposed plan</h3>
      <ol className="strategy-plan-card__steps">
        {plan.steps.map((step) => (
          <li key={step.order}>
            <strong>{step.searchName}</strong>
            {step.rationale !== undefined &&
              step.rationale !== null &&
              step.rationale !== "" && <span> — {step.rationale}</span>}
          </li>
        ))}
      </ol>
      <p className="strategy-plan-card__rationale">{plan.rationale}</p>
      {pendingApprovalPart !== undefined && (
        <ApprovalDialog part={pendingApprovalPart} />
      )}
    </div>
  );
}
