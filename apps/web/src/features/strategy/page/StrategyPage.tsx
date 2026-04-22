"use client";

import { useQuery } from "@tanstack/react-query";
import { redirect } from "next/navigation";
import { useState } from "react";

import { Spinner } from "@/components/ui/spinner";
import { conversationDetailOptions } from "@/lib/api/conversations";
import { StrategyGraph } from "@/features/strategy/graph/components/StrategyGraph";
import { useStrategyStore } from "@/state/strategy/store";

interface StrategyPageProps {
  siteId: string;
  conversationId: string;
  /** When set, the editor sheet auto-opens focused on this step. */
  focusStepId: string | null;
}

export function StrategyPage({
  siteId,
  conversationId,
  focusStepId,
}: StrategyPageProps) {
  const detailQuery = useQuery(conversationDetailOptions(conversationId));
  const setStrategy = useStrategyStore((s) => s.setStrategy);
  const draftStrategy = useStrategyStore((s) => s.strategy);

  const [hydratedFor, setHydratedFor] = useState<string | null>(null);

  const serverStrategy = detailQuery.data ?? null;

  // Render-time hydration: when we receive a fresh server strategy for this
  // conversation, mirror it into the store. Re-runs only when the
  // conversation id changes — subsequent server refetches are ignored so we
  // do not stomp on optimistic edits.
  if (
    detailQuery.isFetched &&
    serverStrategy != null &&
    hydratedFor !== conversationId
  ) {
    setHydratedFor(conversationId);
    setStrategy(serverStrategy);
  }

  if (
    detailQuery.isFetched &&
    serverStrategy === null
  ) {
    redirect(`/${siteId}/conversation`);
  }

  if (detailQuery.isPending) {
    return (
      <div className="flex h-full items-center justify-center bg-card">
        <Spinner className="size-5" />
      </div>
    );
  }

  // Prefer the live store (carries optimistic edits) once hydrated.
  const strategy =
    draftStrategy?.id === conversationId ? draftStrategy : serverStrategy;

  return (
    <div className="flex min-h-0 min-w-0 flex-1">
      <StrategyGraph
        strategy={strategy}
        siteId={siteId}
        showTopbar
        focusStepId={focusStepId}
      />
    </div>
  );
}
