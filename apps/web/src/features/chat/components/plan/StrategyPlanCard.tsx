"use client";

import { useState } from "react";

import { submitProductAction } from "@/lib/api/feedback";
import type {
  InteractivePlan,
  PlanActionRequest,
  PlanStatus,
} from "@/lib/types/plan";
import { usePlanStore } from "@/state/usePlanStore";
import { useSessionStore } from "@/state/useSessionStore";
import { PlanStepItem } from "@/features/chat/components/plan/PlanStepItem";
import { PlanQuestionCard } from "@/features/chat/components/plan/PlanQuestionCard";
import { PlanActions } from "@/features/chat/components/plan/PlanActions";
import {
  storedValuesEqual,
  collectParamEdits,
  collectAnswers,
} from "./strategyPlanCardUtils";

interface StrategyPlanCardProps {
  siteId: string;
  plan: InteractivePlan;
  planTraceId: string | null;
  planMessageGroupId: string | null;
  onSendMessage: (text: string, metadata?: Record<string, unknown>) => void;
  onApprovePlan: (action: PlanActionRequest) => Promise<void>;
}

const statusBadgeColor: Record<PlanStatus, string> = {
  draft: "bg-zinc-500/20 text-zinc-400",
  presented: "bg-yellow-500/20 text-yellow-400",
  approved: "bg-emerald-500/20 text-emerald-400",
  executing: "bg-blue-500/20 text-blue-400",
  complete: "bg-emerald-500/20 text-emerald-400",
  failed: "bg-red-500/20 text-red-400",
};

export function StrategyPlanCard({
  siteId,
  plan,
  planTraceId,
  planMessageGroupId,
  onSendMessage,
  onApprovePlan,
}: StrategyPlanCardProps) {
  const strategyId = useSessionStore((s) => s.strategyId);
  const [localAnswers, setLocalAnswers] = useState<Record<string, unknown>>({});
  const [localParamEdits, setLocalParamEdits] = useState<
    Record<string, Record<string, unknown>>
  >({});
  const [isSubmittingApproval, setIsSubmittingApproval] = useState(false);

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
  const hasUnrelatedUnanswered = unansweredQuestions.some(
    (q) => q.relatedStep == null,
  );

  const isDisabled =
    plan.status === "executing" ||
    plan.status === "complete" ||
    plan.status === "failed";

  const paramEdits = collectParamEdits(localParamEdits);
  const answers = collectAnswers(localAnswers);

  function buildPlanChatMetadata(
    action: string,
    extra: Record<string, unknown> = {},
  ): Record<string, unknown> {
    return {
      action,
      source: "plan_panel",
      planId: plan.id,
      planTraceId,
      planMessageGroupId,
      unansweredQuestionCount: unansweredQuestions.length,
      paramEditCount: paramEdits.length,
      ...extra,
    };
  }

  function handleParamChange(stepId: string, paramName: string, value: unknown) {
    const originalValue = plan.steps.find((step) => step.id === stepId)?.parameters[
      paramName
    ]?.value;
    const unchanged = storedValuesEqual(originalValue, value);

    setLocalParamEdits((prev) => {
      if (!unchanged) {
        return {
          ...prev,
          [stepId]: { ...prev[stepId], [paramName]: value },
        };
      }
      const stepEdits = prev[stepId];
      if (stepEdits == null || !(paramName in stepEdits)) return prev;
      const nextStepEdits = { ...stepEdits };
      delete nextStepEdits[paramName];
      if (Object.keys(nextStepEdits).length > 0) {
        return { ...prev, [stepId]: nextStepEdits };
      }
      const nextEdits = { ...prev };
      delete nextEdits[stepId];
      return nextEdits;
    });
  }

  function handleAnswer(questionId: string, answer: unknown) {
    setLocalAnswers((prev) => ({ ...prev, [questionId]: answer }));
  }

  function handleApprove() {
    if (
      isSubmittingApproval ||
      plan.status === "approved" ||
      plan.status === "executing" ||
      plan.status === "complete" ||
      plan.status === "failed"
    ) {
      return;
    }

    const action: PlanActionRequest = {
      planId: plan.id,
      action: "approve",
      traceId: planTraceId,
      messageGroupId: planMessageGroupId,
      source: "plan_panel",
      paramEdits,
      answers,
    };
    setIsSubmittingApproval(true);
    void onApprovePlan(action).finally(() => {
      setIsSubmittingApproval(false);
    });
  }

  type ProductAction = Parameters<typeof submitProductAction>[0]["action"];

  function sendChatAction(
    action: ProductAction,
    message: string,
    extra: Record<string, unknown> = {},
  ) {
    if (strategyId != null && strategyId !== "") {
      void submitProductAction({
        action,
        streamId: strategyId,
        strategyId,
        planId: plan.id,
        traceId: planTraceId,
        messageGroupId: planMessageGroupId,
        metadata: {
          source: "plan_panel",
          unansweredQuestionCount: unansweredQuestions.length,
          paramEditCount: paramEdits.length,
          ...extra,
        },
      }).catch(() => {});
    }
    onSendMessage(message, buildPlanChatMetadata(action, extra));
  }

  function handleAskQuestion() {
    sendChatAction("plan_ask_question", "I have a question about this plan:");
  }

  function handleSuggestChanges() {
    sendChatAction("plan_suggest_changes", "I'd like to suggest some changes to this plan:");
  }

  function handleReject() {
    sendChatAction(
      "plan_reject",
      "Please discard this plan and propose a different one for the same goal.",
      { planStatus: plan.status },
    );
  }

  function handleRegenerate() {
    sendChatAction(
      "assistant_regenerate",
      "Please regenerate this plan from scratch. Use a different approach if helpful.",
      { scope: "plan", planStatus: plan.status },
    );
  }

  return (
    <div
      data-plan-id={plan.id}
      ref={(node) => {
        if (!node) return;
        const observer = new IntersectionObserver(
          ([entry]) => {
            if (entry) usePlanStore.getState().setPinned(!entry.isIntersecting);
          },
          { threshold: 0.1 },
        );
        observer.observe(node);
        return () => observer.disconnect();
      }}
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
                  siteId={siteId}
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
                steps={plan.steps}
                siteId={siteId}
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
          planStatus={isSubmittingApproval ? "approved" : plan.status}
          onApprove={handleApprove}
          onReject={handleReject}
          onRegenerate={handleRegenerate}
          onAskQuestion={handleAskQuestion}
          onSuggestChanges={handleSuggestChanges}
        />
      </div>
    </div>
  );
}

