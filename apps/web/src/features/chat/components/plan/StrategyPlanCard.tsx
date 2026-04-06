"use client";

import { useState } from "react";

import type { InteractivePlan, PlanStatus, PlanInteractionMetadata } from "@/lib/types/plan";
import { usePlanStore } from "@/state/usePlanStore";
import { PlanStepItem } from "@/features/chat/components/plan/PlanStepItem";
import { PlanQuestionCard } from "@/features/chat/components/plan/PlanQuestionCard";
import { PlanActions } from "@/features/chat/components/plan/PlanActions";

interface StrategyPlanCardProps {
  plan: InteractivePlan;
  onSendMessage: (text: string, metadata?: Record<string, unknown>) => void;
}

const statusBadgeColor: Record<PlanStatus, string> = {
  draft: "bg-zinc-500/20 text-zinc-400",
  presented: "bg-yellow-500/20 text-yellow-400",
  approved: "bg-emerald-500/20 text-emerald-400",
  executing: "bg-blue-500/20 text-blue-400",
  complete: "bg-emerald-500/20 text-emerald-400",
  failed: "bg-red-500/20 text-red-400",
};

export function StrategyPlanCard({ plan, onSendMessage }: StrategyPlanCardProps) {
  const updatePlan = usePlanStore((s) => s.updatePlan);

  const [localAnswers, setLocalAnswers] = useState<Record<string, unknown>>({});
  const [localParamEdits, setLocalParamEdits] = useState<Record<string, Record<string, unknown>>>({});

  const unansweredQuestions = plan.questions.filter(
    (q) => q.answer === null && localAnswers[q.id] === undefined,
  );
  const hasUnansweredQuestions = unansweredQuestions.length > 0;

  // Build the set of step IDs that still have unanswered questions.
  // Only those steps get overridden to "needs_user_input" — the rest
  // stay at their original status so answering one question immediately
  // flips its related step from ? to checkmark.
  const stepsWithUnanswered = new Set(
    unansweredQuestions
      .map((q) => q.relatedStep)
      .filter((id): id is string => id != null),
  );
  // Questions without a relatedStep block ALL steps (conservative).
  const hasUnrelatedUnanswered = unansweredQuestions.some((q) => q.relatedStep == null);

  const isDisabled = plan.status === "executing" || plan.status === "complete" || plan.status === "failed";


  function handleParamChange(stepId: string, paramName: string, value: unknown) {
    setLocalParamEdits((prev) => ({
      ...prev,
      [stepId]: { ...prev[stepId], [paramName]: value },
    }));
  }

  function handleAnswer(questionId: string, answer: unknown) {
    setLocalAnswers((prev) => ({ ...prev, [questionId]: answer }));
  }

  function handleApprove() {
    // Guard against double-click: update status first to disable the button.
    if (plan.status === "approved" || plan.status === "executing" || plan.status === "complete" || plan.status === "failed") return;
    updatePlan({ status: "approved" });

    // Batch all edits, answers, and approval into a single message so the
    // model receives one turn instead of N separate turns.
    const paramEdits: Array<{ stepId: string; paramName: string; newValue: unknown }> = [];
    for (const [stepId, params] of Object.entries(localParamEdits)) {
      for (const [paramName, newValue] of Object.entries(params)) {
        paramEdits.push({ stepId, paramName, newValue });
      }
    }

    const answers: Array<{ questionId: string; answer: unknown }> = [];
    for (const [questionId, answer] of Object.entries(localAnswers)) {
      answers.push({ questionId, answer });
    }

    const metadata: PlanInteractionMetadata = {
      type: "plan_interaction",
      planId: plan.id,
      action: "approve",
      data: { paramEdits, answers },
    };

    const text = `[Plan interaction: approve]`;
    const payload: Record<string, unknown> = { planInteraction: metadata };
    onSendMessage(text, payload);
  }

  function handleAskQuestion() {
    onSendMessage("I have a question about this plan:");
  }

  function handleSuggestChanges() {
    onSendMessage("I'd like to suggest some changes to this plan:");
  }

  return (
    <div
      data-plan-id={plan.id}
      className="rounded-lg border border-purple-500/30 bg-card"
    >
      {/* Header */}
      <div className="border-b border-border px-3 py-2.5 space-y-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-purple-400">Strategy Plan</span>
          <span
            className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none ${statusBadgeColor[plan.status]}`}
          >
            {plan.status}
          </span>
          <span className="ml-auto text-[10px] tabular-nums text-muted-foreground">
            v{plan.version}
          </span>
        </div>
        <h3 className="text-sm font-medium text-foreground">{plan.title}</h3>
        <p className="text-xs leading-snug text-muted-foreground">{plan.description}</p>
      </div>

      <div className="space-y-4 px-3 py-2.5">
        {/* Steps */}
        {plan.steps.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Steps ({plan.steps.length})
            </h4>
            {plan.steps.map((step, idx) => {
              const stepBlocked =
                (hasUnrelatedUnanswered || stepsWithUnanswered.has(step.id)) &&
                step.status === "ready";
              const effectiveStep = stepBlocked
                ? { ...step, status: "needs_user_input" as const }
                : step;
              return (
                <PlanStepItem
                  key={step.id}
                  step={effectiveStep}
                  index={idx}
                  onParamChange={handleParamChange}
                  disabled={isDisabled}
                />
              );
            })}
          </div>
        )}

        {/* Questions — hide answered ones */}
        {unansweredQuestions.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Questions ({unansweredQuestions.length})
            </h4>
            {unansweredQuestions.map((q) => (
              <PlanQuestionCard
                key={q.id}
                question={q}
                onAnswer={handleAnswer}
                disabled={isDisabled}
              />
            ))}
          </div>
        )}

        {/* Uncertainties */}
        {plan.uncertainties.length > 0 && (
          <div className="space-y-1">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Uncertainties
            </h4>
            <ul className="list-disc space-y-0.5 pl-4">
              {plan.uncertainties.map((u) => (
                <li key={u} className="text-xs leading-snug text-muted-foreground">
                  {u}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Actions */}
        <PlanActions
          hasUnansweredQuestions={hasUnansweredQuestions}
          planStatus={plan.status}
          onApprove={handleApprove}
          onAskQuestion={handleAskQuestion}
          onSuggestChanges={handleSuggestChanges}
        />
      </div>
    </div>
  );
}
