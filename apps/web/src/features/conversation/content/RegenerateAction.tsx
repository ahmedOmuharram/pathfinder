"use client";

import { useAuiState } from "@assistant-ui/react";
import { RefreshCw } from "lucide-react";

import { submitProductAction } from "@pathfinder/shared/generated/hooks/useSubmitProductAction";
import { MessageAction } from "@/components/ai-elements/message";

import { extractTraceId } from "../runtime/traceId";

export function RegenerateAction(props: { onClick?: (e: React.MouseEvent) => void }) {
  const message = useAuiState((s) => s.message);
  const handleClick = (e: React.MouseEvent) => {
    const traceId = extractTraceId(message);
    void submitProductAction({
      action: "assistant_regenerate",
      streamId: message.id,
      ...(traceId !== null && { traceId }),
    }).catch((err: unknown) => {
      console.warn("submitProductAction(assistant_regenerate) failed", err);
    });
    props.onClick?.(e);
  };
  return (
    <MessageAction tooltip="Regenerate" onClick={handleClick}>
      <RefreshCw />
    </MessageAction>
  );
}
