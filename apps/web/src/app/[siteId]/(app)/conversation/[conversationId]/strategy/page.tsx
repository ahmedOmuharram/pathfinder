"use client";

import { use } from "react";

import { StrategyPage } from "@/features/strategy/page/StrategyPage";

export default function StrategyRoute({
  params,
}: {
  params: Promise<{ siteId: string; conversationId: string }>;
}) {
  const { siteId, conversationId } = use(params);
  return (
    <StrategyPage
      siteId={siteId}
      conversationId={conversationId}
      focusStepId={null}
    />
  );
}
