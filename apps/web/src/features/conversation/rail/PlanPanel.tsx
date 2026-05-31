"use client";

import type { UIMessage } from "ai";
import type { PlanArtifact, PlannedStep } from "@pathfinder/shared";
import { ChevronLeft, ChevronRight, ClipboardList } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";

import { useChatHelpers } from "../runtime/chatHelpersContext";
import {
  ApprovalBar,
  handleApprove,
  handleAskQuestion,
  handleDeny,
  handleSuggestChanges,
  type PendingApprovalInfo,
  type SlotAnswerEntry,
} from "./planPanelActions";
import { PlanSlotForms, buildSlotAnswers, slotsAreFilled } from "./PlanSlotForm";
import { RailEmptyState, RailPanelShell } from "./RailPanelShell";

function collectPlans(messages: UIMessage[]): PlanArtifact[] {
  const plans: PlanArtifact[] = [];
  for (const message of messages) {
    if (message.role !== "assistant") continue;
    for (const part of message.parts) {
      if (part.type !== "data-plan-artifact") continue;
      const data = (part as { data?: PlanArtifact }).data;
      if (data != null) plans.push(data);
    }
  }
  return plans;
}

function findPendingApproval(messages: UIMessage[]): PendingApprovalInfo | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    if (message?.role !== "assistant") continue;
    for (const part of message.parts) {
      if (
        part.type === "tool-submit_plan" &&
        "state" in part &&
        part.state === "approval-requested" &&
        "approval" in part
      ) {
        const input =
          "input" in part ? (part.input as { planId?: string } | undefined) : undefined;
        return {
          approvalId: part.approval.id,
          planId: input?.planId ?? null,
          sourceMessage: message,
        };
      }
    }
  }
  return null;
}

export function PlanPanel() {
  const chat = useChatHelpers();
  const plans = collectPlans(chat.messages);
  const pending = findPendingApproval(chat.messages);

  // Local focused index — defaults to latest plan; user can navigate back.
  const latestIndex = Math.max(0, plans.length - 1);
  const [focusedIndex, setFocusedIndexState] = useState(latestIndex);
  const [prevPlanCount, setPrevPlanCount] = useState(plans.length);
  if (plans.length !== prevPlanCount) {
    setPrevPlanCount(plans.length);
    // On new plan arrival, jump focus to latest (render-time pattern, no useEffect).
    setFocusedIndexState(latestIndex);
  }
  const [slotValues, setSlotValues] = useState<Record<string, unknown>>({});
  const setFocusedIndex = (index: number) => {
    if (plans.length === 0) {
      setFocusedIndexState(0);
      return;
    }
    setFocusedIndexState(Math.max(0, Math.min(index, plans.length - 1)));
  };
  const focused = plans[focusedIndex] ?? null;
  const isLatest = focusedIndex === plans.length - 1;
  const slots = focused?.slots ?? [];
  const fillableSlots = slots.filter((s) => s.status !== "needs_discovery");
  const allFilled = slotsAreFilled(slots, slotValues);

  return (
    <RailPanelShell title="Plan">
      {focused == null ? (
        <RailEmptyState
          icon={<ClipboardList className="h-8 w-8" aria-hidden />}
          heading="No plan proposed yet"
          description="The planning agent will propose a reviewable plan here. Approve or reject it before execution."
        />
      ) : (
        <div className="space-y-3 p-3 text-sm">
          {plans.length > 1 && (
            <CarouselNav
              count={plans.length}
              focusedIndex={focusedIndex}
              onChange={setFocusedIndex}
            />
          )}
          {pending != null && isLatest && slots.length > 0 && (
            <PlanSlotForms
              slots={slots}
              values={slotValues}
              onChange={(key, value) =>
                setSlotValues((prev) => ({ ...prev, [key]: value }))
              }
            />
          )}
          {pending != null && isLatest && (
            <ApprovalBar
              pending={pending}
              approveDisabled={fillableSlots.length > 0 && !allFilled}
              onApprove={() => {
                const answers: SlotAnswerEntry[] =
                  fillableSlots.length > 0 ? buildSlotAnswers(slots, slotValues) : [];
                handleApprove(chat, pending, answers);
                setSlotValues({});
              }}
              onDeny={() => handleDeny(chat, pending)}
              onSuggestChanges={(text) => handleSuggestChanges(chat, pending, text)}
              onAskQuestion={(text) => handleAskQuestion(chat, pending, text)}
            />
          )}
          {(pending == null || !isLatest) && plans.length > 0 && (
            <div className="rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
              {isLatest
                ? "View only — awaiting next user input."
                : "Older plan version (read-only)."}
            </div>
          )}
          {focused.rationale !== "" && (
            <section>
              <h3 className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                Rationale
              </h3>
              <p className="text-xs leading-relaxed text-foreground">
                {focused.rationale}
              </p>
            </section>
          )}
          <section>
            <h3 className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              {focused.steps.length} {focused.steps.length === 1 ? "step" : "steps"}
            </h3>
            <ol className="space-y-3">
              {focused.steps.map((step, idx) => (
                <PlanStepCard
                  key={`${step.searchName}-${idx}`}
                  step={step}
                  index={idx}
                />
              ))}
            </ol>
          </section>
        </div>
      )}
    </RailPanelShell>
  );
}

function CarouselNav({
  count,
  focusedIndex,
  onChange,
}: {
  count: number;
  focusedIndex: number;
  onChange: (index: number) => void;
}) {
  return (
    <div
      data-testid="plan-carousel-nav"
      className="flex items-center justify-between gap-2 rounded-md border border-border bg-muted/30 px-2 py-1"
    >
      <Button
        type="button"
        size="icon-xs"
        variant="ghost"
        disabled={focusedIndex === 0}
        onClick={() => onChange(focusedIndex - 1)}
        aria-label="Previous plan"
      >
        <ChevronLeft className="size-4" />
      </Button>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>
          v{focusedIndex + 1} of {count}
        </span>
        <div className="flex gap-1">
          {Array.from({ length: count }).map((_, i) => (
            <button
              key={i}
              type="button"
              data-testid={`plan-carousel-dot-${i}`}
              aria-label={`Plan v${i + 1}`}
              className={cn(
                "h-1.5 w-1.5 rounded-full transition-colors",
                i === focusedIndex
                  ? "bg-foreground"
                  : "bg-muted-foreground/40 hover:bg-muted-foreground",
              )}
              onClick={() => onChange(i)}
            />
          ))}
        </div>
      </div>
      <Button
        type="button"
        size="icon-xs"
        variant="ghost"
        disabled={focusedIndex >= count - 1}
        onClick={() => onChange(focusedIndex + 1)}
        aria-label="Next plan"
      >
        <ChevronRight className="size-4" />
      </Button>
    </div>
  );
}

function PlanStepCard({ step, index }: { step: PlannedStep; index: number }) {
  const params = step.parameters ?? {};
  const paramEntries = Object.entries(params).filter(
    ([, value]) => value !== null && value !== undefined && value !== "",
  );
  return (
    <li className="rounded-md border border-border bg-card/60 p-2.5">
      <div className="flex items-baseline gap-2">
        <span className="text-xs font-semibold text-muted-foreground tabular-nums">
          {index + 1}.
        </span>
        <span className="break-all font-mono text-xs text-foreground">
          {step.searchName}
        </span>
      </div>
      {step.rationale != null && step.rationale !== "" && (
        <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
          {step.rationale}
        </p>
      )}
      {paramEntries.length > 0 && (
        <dl className="mt-2 space-y-1 border-t border-border/60 pt-2">
          {paramEntries.map(([key, value]) => (
            <div key={key} className="flex gap-2 text-[11px]">
              <dt className="w-32 shrink-0 break-all font-mono text-muted-foreground">
                {key}
              </dt>
              <dd className="min-w-0 flex-1 break-words font-mono text-foreground">
                {formatParamValue(value)}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </li>
  );
}

function formatParamValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}
