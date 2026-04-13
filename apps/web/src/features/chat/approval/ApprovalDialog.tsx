"use client";

/**
 * Modal-style approval dialog for AI SDK v6 tool-approval requests.
 *
 * Used as the primary UX for prominent approvals (e.g., the propose_plan
 * approval flow rendered by `StrategyPlanCard` in Task 5g). Inline approvals
 * are handled by `ToolCallPart`'s `ApprovalActions`.
 *
 * Reads `addToolApprovalResponse` from the `ChatSessionContext` so the dialog
 * can be rendered anywhere inside the chat tree without prop drilling.
 */

import type { PathfinderUIMessage } from "@pathfinder/shared";

import { useChatSessionContext } from "./useChatContext";

type ApprovalPart = Extract<
  PathfinderUIMessage["parts"][number],
  { state: "approval-requested" }
>;

function deriveToolName(part: ApprovalPart): string {
  if (part.type === "dynamic-tool") {
    return part.toolName;
  }
  return part.type.replace(/^tool-/, "");
}

export function ApprovalDialog({ part }: { part: ApprovalPart }) {
  const { addToolApprovalResponse } = useChatSessionContext();
  const toolName = deriveToolName(part);
  // `addToolApprovalResponse` returns `void | PromiseLike<void>`; wrap calls
  // in void-returning arrows so React's onClick (which expects void) gets the
  // right shape and the (possible) promise is intentionally fire-and-forget.
  const onAllow = (): void => {
    void addToolApprovalResponse({ id: part.toolCallId, approved: true });
  };
  const onDeny = (): void => {
    void addToolApprovalResponse({ id: part.toolCallId, approved: false });
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="approval-dialog"
      data-tool={toolName}
    >
      <h3 className="approval-dialog__title">Approve {toolName}?</h3>
      <pre className="approval-dialog__input">
        <code>{JSON.stringify(part.input, null, 2)}</code>
      </pre>
      <div className="approval-dialog__actions">
        <button type="button" onClick={onDeny}>
          Deny
        </button>
        <button type="button" onClick={onAllow}>
          Allow
        </button>
      </div>
    </div>
  );
}
