"use client";

import type { DataOptimizeLaunchPayload } from "@pathfinder/shared";
import { Zap } from "lucide-react";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { OptimizeApplyButton } from "./OptimizeApplyButton";

const ROUTE_RE = /^\/[^/]+\/conversation\/([^/?#]+)/;

export function OptimizeLaunchPart({ data }: { data: DataOptimizeLaunchPayload }) {
  const { stepId, paramKeys, criterion, budget, modelId, taskId, localStepId } = data;
  // `usePathname()` returns null in jsdom unit tests where there is no
  // App Router context. The Apply button just doesn't render in that case.
  const pathname = usePathname() as string | null;
  const match = pathname != null ? pathname.match(ROUTE_RE) : null;
  const conversationId = match?.[1] ?? null;
  return (
    <div
      data-testid="data-optimize-launch"
      className="my-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs dark:border-amber-800 dark:bg-amber-950"
    >
      <div className="flex items-center gap-2">
        <Zap className="size-3.5 text-amber-600 dark:text-amber-400" aria-hidden />
        <span className="text-sm font-medium">Optimize launch</span>
        <span className="ml-auto text-muted-foreground">step {stepId}</span>
      </div>
      <dl className="mt-2 space-y-1">
        <Row label="Params">
          <span className="font-mono text-[11px]">{paramKeys.join(", ")}</span>
        </Row>
        <Row label="Criterion">
          <span className="text-[11px] leading-snug">{criterion}</span>
        </Row>
        <Row label="Budget">
          <span className="text-[11px] tabular-nums">{budget} trials</span>
        </Row>
        {modelId != null && modelId !== "" ? (
          <Row label="Model">
            <span className="font-mono text-[11px]">{modelId}</span>
          </Row>
        ) : null}
      </dl>
      {conversationId !== null
        && taskId != null
        && taskId !== ""
        && localStepId != null
        && localStepId !== "" ? (
        <OptimizeApplyButton
          conversationId={conversationId}
          taskId={taskId}
          localStepId={localStepId}
        />
      ) : null}
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex gap-2 text-[11px]">
      <dt className="w-20 shrink-0 text-muted-foreground">{label}:</dt>
      <dd className="min-w-0 flex-1 break-words text-foreground">{children}</dd>
    </div>
  );
}
