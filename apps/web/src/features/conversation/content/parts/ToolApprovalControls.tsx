"use client";

import { getToolName, isToolUIPart, type ToolUIPart, type UIMessage } from "ai";
import { Check, ShieldAlert, X } from "lucide-react";
import { toast } from "sonner";

import { ToolInput } from "@/components/ai-elements/tool";
import { Button } from "@/components/ui/button";
import { humanizeToolName } from "@/lib/utils/toolNames";

import { useChatHelpersOptional } from "../../runtime/chatHelpersContext";

// The consult carousel answers this tool's approval with the user's answers.
const CONSULT_TOOL_NAME = "consult_user";

export type ApprovalDecision = "pending" | "approved" | "denied";

export interface ToolApprovalView {
  approvalId: string;
  toolName: string;
  input: ToolUIPart["input"];
  decision: ApprovalDecision;
}

function decisionOf(
  state: ToolUIPart["state"],
  approved: boolean | undefined,
): ApprovalDecision {
  if (state === "approval-requested") return "pending";
  return approved === true ? "approved" : "denied";
}

/** The approval carried by one tool call, across every message in the thread. */
export function findToolApproval(
  messages: UIMessage[],
  toolCallId: string,
): ToolApprovalView | null {
  for (const message of messages) {
    for (const part of message.parts) {
      if (!isToolUIPart(part) || part.toolCallId !== toolCallId) continue;
      const approval = part.approval;
      if (approval === undefined) continue;
      return {
        approvalId: approval.id,
        toolName: getToolName(part),
        input: part.input,
        decision: decisionOf(part.state, approval.approved),
      };
    }
  }
  return null;
}

export function ToolApprovalControls({ toolCallId }: { toolCallId: string }) {
  const chat = useChatHelpersOptional();
  if (chat === null) return null;
  const approval = findToolApproval(chat.messages, toolCallId);
  if (approval === null || approval.toolName === CONSULT_TOOL_NAME) return null;

  if (approval.decision !== "pending") {
    const approved = approval.decision === "approved";
    return (
      <div
        data-testid="tool-approval-decision"
        className={`flex items-center gap-1.5 px-3 pb-2 text-xs ${
          approved ? "text-success" : "text-destructive"
        }`}
      >
        {approved ? (
          <Check className="size-3.5" aria-hidden />
        ) : (
          <X className="size-3.5" aria-hidden />
        )}
        {approved ? "Approved" : "Denied"}
      </div>
    );
  }

  const respond = (approved: boolean) => {
    Promise.resolve(
      chat.addToolApprovalResponse({ id: approval.approvalId, approved }),
    ).catch(() => {
      toast.error("Approval could not be sent");
    });
  };

  return (
    <div
      data-testid="tool-approval-controls"
      className="mx-3 mb-3 space-y-2 rounded-md border border-warning/40 bg-warning/10 p-2"
    >
      <p className="flex items-center gap-1.5 text-xs font-medium">
        <ShieldAlert className="size-3.5 text-warning" aria-hidden />
        {humanizeToolName(approval.toolName)} needs your approval before it runs.
      </p>
      <ToolInput input={approval.input} className="p-0" />
      <div className="flex justify-end gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => respond(false)}
          data-testid="tool-approval-deny"
        >
          <X className="mr-1 size-3.5" aria-hidden /> Deny
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={() => respond(true)}
          data-testid="tool-approval-approve"
        >
          <Check className="mr-1 size-3.5" aria-hidden /> Approve
        </Button>
      </div>
    </div>
  );
}
