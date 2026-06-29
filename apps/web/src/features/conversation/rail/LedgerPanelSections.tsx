"use client";

import type {
  LedgerBuildPayload,
  LedgerFramePayload,
  LedgerIntentPayload,
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
  return (
    <LedgerSection title="Frame">
      <LedgerRow label="present" value={<BoolBadge value={frame.present} />} />
      <LedgerRow
        label="criteria"
        value={
          <CountChip
            value={frame.criteriaCount}
            tone={frame.criteriaCount > 0 ? "good" : "neutral"}
          />
        }
      />
      <LedgerRow label="bound" value={<CountChip value={frame.boundCount} />} />
      <LedgerRow
        label="open slots"
        value={
          <CountChip
            value={frame.openSlotCount}
            tone={frame.openSlotCount > 0 ? "warn" : "neutral"}
          />
        }
      />
      <LedgerRow
        label="dropped"
        value={
          <CountChip
            value={frame.droppedCount}
            tone={frame.droppedCount > 0 ? "warn" : "neutral"}
          />
        }
      />
      <LedgerRow label="needs user" value={<BoolBadge value={frame.needsUser} />} />
      <LedgerRow
        label="ready to build"
        value={<BoolBadge value={frame.readyToBuild} />}
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
