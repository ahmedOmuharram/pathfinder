"use client";

import { use } from "react";

import { StrategyPage } from "@/features/strategy/page/StrategyPage";

export default function StrategyStepRoute({
  params,
}: {
  params: Promise<{ siteId: string; conversationId: string; stepId: string }>;
}) {
  const { siteId, conversationId, stepId } = use(params);
  return (
    <StrategyPage
      siteId={siteId}
      conversationId={conversationId}
      focusStepId={stepId}
    />
  );
}
