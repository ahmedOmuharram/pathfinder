"use client";

import { use } from "react";

import { EdaWorkbench } from "@/features/eda/EdaWorkbench";

export default function EdaRoute({
  params,
}: {
  params: Promise<{ siteId: string; conversationId: string }>;
}) {
  const { siteId, conversationId } = use(params);
  return <EdaWorkbench siteId={siteId} conversationId={conversationId} />;
}
