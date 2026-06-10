"use client";

import type { UIMessage } from "ai";
import { Check, ChevronRight, HelpCircle, PencilLine, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { submitProductAction } from "@pathfinder/shared/generated/hooks/useSubmitProductAction";
import { cn } from "@/lib/utils/cn";
import { usePlanStore } from "@/state/usePlanStore";

import { extractTraceIdFromUIMessage } from "../runtime/traceIdFromUIMessage";

export interface PendingApprovalInfo {
  approvalId: string;
  planId: string | null;
  sourceMessage: UIMessage;
}

export type SlotAnswerEntry = {
  stepId: string;
  paramName: string;
  value: unknown;
};

export type ChatHelpersForApproval = {
  addToolApprovalResponse: (args: {
    id: string;
    approved: boolean;
    reason?: string;
  }) => void;
  sendMessage: (message: { text: string }) => void;
  setMessages: (
    messages: UIMessage[] | ((messages: UIMessage[]) => UIMessage[]),
  ) => void;
};

function fireProductAction(
  action: string,
  pending: PendingApprovalInfo,
  metadata?: Record<string, unknown>,
): void {
  const traceId = extractTraceIdFromUIMessage(pending.sourceMessage);
  const body: Parameters<typeof submitProductAction>[0] = {
    action: action as Parameters<typeof submitProductAction>[0]["action"],
    streamId: pending.sourceMessage.id,
    ...(traceId !== null && { traceId }),
    ...(pending.planId !== null && { planId: pending.planId }),
    ...(metadata !== undefined && { metadata }),
  };
  void submitProductAction(body).catch((err: unknown) => {
    console.warn("submitProductAction failed", action, err);
  });
}

export function handleApprove(
  chat: ChatHelpersForApproval,
  pending: PendingApprovalInfo,
  slotAnswers: SlotAnswerEntry[] = [],
): void {
  if (slotAnswers.length > 0) {
    attachSlotAnswersToSourceMessage(chat, pending, slotAnswers);
  }
  chat.addToolApprovalResponse({ id: pending.approvalId, approved: true });
  usePlanStore.getState().resolvePendingApproval();
  fireProductAction("plan_approve", pending, { slotCount: slotAnswers.length });
}

export const PLAN_SLOT_ANSWERS_PART_TYPE = "data-plan-slot-answers";

function attachSlotAnswersToSourceMessage(
  chat: ChatHelpersForApproval,
  pending: PendingApprovalInfo,
  slotAnswers: SlotAnswerEntry[],
): void {
  const slotPart: UIMessage["parts"][number] = {
    type: PLAN_SLOT_ANSWERS_PART_TYPE,
    data: {
      toolCallId: pending.approvalId,
      answers: slotAnswers.map((a) => ({
        stepId: a.stepId,
        paramName: a.paramName,
        value: a.value,
      })),
    },
  } as unknown as UIMessage["parts"][number];

  chat.setMessages((messages) =>
    messages.map((msg) => {
      if (msg.id !== pending.sourceMessage.id) return msg;
      const filtered = msg.parts.filter((p) => p.type !== PLAN_SLOT_ANSWERS_PART_TYPE);
      return { ...msg, parts: [...filtered, slotPart] };
    }),
  );
}

export function handleDeny(
  chat: ChatHelpersForApproval,
  pending: PendingApprovalInfo,
): void {
  chat.addToolApprovalResponse({ id: pending.approvalId, approved: false });
  usePlanStore.getState().resolvePendingApproval();
  fireProductAction("plan_reject", pending);
}

export function handleSuggestChanges(
  chat: ChatHelpersForApproval,
  pending: PendingApprovalInfo,
  text: string,
): void {
  chat.sendMessage({ text });
  fireProductAction("plan_suggest_changes", pending, { text });
}

export function handleAskQuestion(
  chat: ChatHelpersForApproval,
  pending: PendingApprovalInfo,
  text: string,
): void {
  chat.sendMessage({ text });
  fireProductAction("plan_ask_question", pending, { text });
}

export function ApprovalBar({
  pending,
  approveDisabled = false,
  onApprove,
  onDeny,
  onSuggestChanges,
  onAskQuestion,
}: {
  pending: PendingApprovalInfo;
  approveDisabled?: boolean;
  onApprove: () => void;
  onDeny: () => void;
  onSuggestChanges: (text: string) => void;
  onAskQuestion: (text: string) => void;
}) {
  const [suggestText, setSuggestText] = useState("");
  const [askText, setAskText] = useState("");
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [askOpen, setAskOpen] = useState(false);

  return (
    <div className="space-y-2 rounded-md border border-border bg-muted/40 p-2">
      <div className="flex gap-2">
        <Button
          type="button"
          size="sm"
          variant="default"
          onClick={onApprove}
          disabled={approveDisabled}
          className="flex-1"
          data-testid="plan-approve"
          data-approval-id={pending.approvalId}
        >
          <Check className="mr-1 size-4" aria-hidden /> Approve
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onDeny}
          className="flex-1"
          data-testid="plan-deny"
        >
          <X className="mr-1 size-4" aria-hidden /> Deny
        </Button>
      </div>

      <CollapsibleTextareaAction
        open={suggestOpen}
        onOpenChange={setSuggestOpen}
        icon={<PencilLine className="size-3.5" aria-hidden />}
        label="Suggest changes"
        placeholder="Describe what to change..."
        text={suggestText}
        onTextChange={setSuggestText}
        testIdPrefix="plan-suggest"
        onSubmit={() => {
          const text = suggestText.trim();
          if (text === "") return;
          onSuggestChanges(text);
          setSuggestText("");
          setSuggestOpen(false);
        }}
      />

      <CollapsibleTextareaAction
        open={askOpen}
        onOpenChange={setAskOpen}
        icon={<HelpCircle className="size-3.5" aria-hidden />}
        label="Ask a question"
        placeholder="What would you like to know?"
        text={askText}
        onTextChange={setAskText}
        testIdPrefix="plan-ask"
        onSubmit={() => {
          const text = askText.trim();
          if (text === "") return;
          onAskQuestion(text);
          setAskText("");
          setAskOpen(false);
        }}
      />
    </div>
  );
}

function CollapsibleTextareaAction({
  open,
  onOpenChange,
  icon,
  label,
  placeholder,
  text,
  onTextChange,
  onSubmit,
  testIdPrefix,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  icon: React.ReactNode;
  label: string;
  placeholder: string;
  text: string;
  onTextChange: (text: string) => void;
  onSubmit: () => void;
  testIdPrefix: string;
}) {
  return (
    <div className="rounded-md border border-border bg-card/40">
      <button
        type="button"
        onClick={() => onOpenChange(!open)}
        className="flex w-full items-center gap-2 px-2 py-1.5 text-left text-xs font-medium text-foreground hover:bg-muted/40"
        data-testid={`${testIdPrefix}-toggle`}
        aria-expanded={open}
      >
        {icon}
        {label}
        <ChevronRight
          className={cn(
            "ml-auto size-3.5 text-muted-foreground transition-transform",
            open && "rotate-90",
          )}
          aria-hidden
        />
      </button>
      {open && (
        <div className="space-y-2 border-t border-border/60 p-2">
          <Textarea
            value={text}
            onChange={(e) => onTextChange(e.target.value)}
            placeholder={placeholder}
            rows={3}
            data-testid={`${testIdPrefix}-input`}
          />
          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              onClick={onSubmit}
              disabled={text.trim() === ""}
              data-testid={`${testIdPrefix}-send`}
            >
              Send
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
