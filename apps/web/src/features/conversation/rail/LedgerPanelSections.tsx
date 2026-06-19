"use client";

import type {
  LedgerBuildPayload,
  LedgerDiscoveryPayload,
  LedgerFramePayload,
  LedgerIntentPayload,
  LedgerPlanPayload,
  LedgerVerificationPayload,
} from "@pathfinder/shared";

import { type Tone } from "@/lib/utils/statusTone";

import {
  BoolBadge,
  CountChip,
  LedgerRow,
  LedgerSection,
  StatusPill,
} from "./LedgerPanelPrimitives";

export function IntentSection({
  intent,
}: {
  intent: LedgerIntentPayload | null | undefined;
}) {
  if (intent == null) {
    return (
      <LedgerSection title="Intent">
        <p className="text-xs text-muted-foreground">Not classified yet.</p>
      </LedgerSection>
    );
  }
  return (
    <LedgerSection title="Intent">
      <LedgerRow
        label="classification"
        value={<StatusPill text={intent.classification} />}
      />
      <LedgerRow
        label="differential"
        value={<BoolBadge value={intent.isDifferential} />}
      />
      <div className="text-xs leading-relaxed">
        <span className="text-muted-foreground">goal: </span>
        <span className="text-foreground">{intent.inferredGoal}</span>
      </div>
      {intent.isDifferential && intent.differentialSides.length > 0 && (
        <div className="flex flex-wrap items-center gap-1">
          <span className="text-xs text-muted-foreground">sides:</span>
          {intent.differentialSides.map((side) => (
            <StatusPill key={side} text={side} tone="warn" />
          ))}
        </div>
      )}
    </LedgerSection>
  );
}

export function FrameSection({ frame }: { frame: LedgerFramePayload }) {
  const blockingTone: Tone =
    frame.blockingQuestionsUnanswered.length > 0 ? "warn" : "neutral";
  return (
    <LedgerSection title="Frame">
      <LedgerRow label="needed" value={<BoolBadge value={frame.needed} />} />
      <LedgerRow label="blocked" value={<BoolBadge value={frame.blocked} />} />
      <LedgerRow
        label="blocking questions"
        value={
          <CountChip
            value={frame.blockingQuestionsUnanswered.length}
            tone={blockingTone}
          />
        }
      />
      {frame.blockingQuestionsUnanswered.slice(0, 3).map((q, i) => (
        <p
          key={i}
          className="ml-1 border-l border-border pl-2 text-[11px] italic text-muted-foreground"
        >
          {q.question}
        </p>
      ))}
    </LedgerSection>
  );
}

export function DiscoverySection({ discovery }: { discovery: LedgerDiscoveryPayload }) {
  return (
    <LedgerSection title="Discovery">
      <LedgerRow
        label="selected"
        value={
          <CountChip
            value={discovery.selectedCount}
            tone={discovery.selectedCount > 0 ? "good" : "neutral"}
          />
        }
      />
      <LedgerRow
        label="rejected"
        value={<CountChip value={discovery.rejectedCount} />}
      />
      <LedgerRow
        label="intent satisfied"
        value={<BoolBadge value={discovery.intentSatisfied} />}
      />
      <LedgerRow
        label="needs more"
        value={<BoolBadge value={discovery.needsMoreDiscovery} />}
      />
      {discovery.intentGap !== null && discovery.intentGap !== "" && (
        <p className="ml-1 border-l border-warning/40 pl-2 text-[11px] italic text-warning">
          gap: {discovery.intentGap}
        </p>
      )}
    </LedgerSection>
  );
}

export function PlanSection({ plan }: { plan: LedgerPlanPayload }) {
  const blockedTone: Tone =
    plan.blockedKind === "none"
      ? "good"
      : plan.blockedKind === "needs_approval"
        ? "warn"
        : "bad";
  return (
    <LedgerSection title="Plan">
      <LedgerRow label="present" value={<BoolBadge value={plan.plan !== null} />} />
      <LedgerRow label="approved" value={<BoolBadge value={plan.approved} />} />
      <LedgerRow
        label="open user-input slots"
        value={
          <CountChip
            value={plan.openUserInputSlots.length}
            tone={plan.openUserInputSlots.length > 0 ? "warn" : "neutral"}
          />
        }
      />
      <LedgerRow
        label="open discovery slots"
        value={
          <CountChip
            value={plan.openDiscoverySlots.length}
            tone={plan.openDiscoverySlots.length > 0 ? "warn" : "neutral"}
          />
        }
      />
      <LedgerRow
        label="blocked kind"
        value={<StatusPill text={plan.blockedKind} tone={blockedTone} />}
      />
      <LedgerRow
        label="ready to execute"
        value={<BoolBadge value={plan.readyToExecute} />}
      />
    </LedgerSection>
  );
}

export function BuildSection({ build }: { build: LedgerBuildPayload }) {
  const recoveryTone: Tone =
    build.recoveryKind === "none"
      ? "neutral"
      : build.recoveryKind === "transient_retry"
        ? "warn"
        : "bad";
  return (
    <LedgerSection title="Build">
      <LedgerRow
        label="pushed"
        value={
          <CountChip
            value={build.pushedCount}
            tone={build.pushedCount > 0 ? "good" : "neutral"}
          />
        }
      />
      <LedgerRow
        label="failed"
        value={
          <CountChip
            value={build.failedCount}
            tone={build.failedCount > 0 ? "bad" : "neutral"}
          />
        }
      />
      <LedgerRow
        label="skipped"
        value={
          <CountChip
            value={build.skippedCount}
            tone={build.skippedCount > 0 ? "warn" : "neutral"}
          />
        }
      />
      <LedgerRow
        label="zero-result steps"
        value={
          <CountChip
            value={build.zeroResultSteps.length}
            tone={build.zeroResultSteps.length > 0 ? "warn" : "neutral"}
          />
        }
      />
      <LedgerRow
        label="needs recovery"
        value={<BoolBadge value={build.needsRecovery} />}
      />
      <LedgerRow
        label="recovery kind"
        value={<StatusPill text={build.recoveryKind} tone={recoveryTone} />}
      />
      <LedgerRow label="succeeded" value={<BoolBadge value={build.succeeded} />} />
    </LedgerSection>
  );
}

export function VerificationSection({
  verification,
}: {
  verification: LedgerVerificationPayload;
}) {
  return (
    <LedgerSection title="Verification">
      <LedgerRow label="complete" value={<BoolBadge value={verification.complete} />} />
      <LedgerRow
        label="successful"
        value={<BoolBadge value={verification.successful} />}
      />
    </LedgerSection>
  );
}

export function SubAgentCountSection({
  thisTurn,
  total,
}: {
  thisTurn: number;
  total: number;
}) {
  return (
    <LedgerSection title="Sub-agent calls">
      <LedgerRow label="this turn" value={<CountChip value={thisTurn} />} />
      <LedgerRow label="total" value={<CountChip value={total} />} />
    </LedgerSection>
  );
}
