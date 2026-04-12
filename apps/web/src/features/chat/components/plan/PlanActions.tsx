"use client";

interface PlanActionsProps {
  hasUnansweredQuestions: boolean;
  planStatus: string;
  onApprove: () => void;
  onReject: () => void;
  onRegenerate: () => void;
  onAskQuestion: () => void;
  onSuggestChanges: () => void;
}

export function PlanActions({
  hasUnansweredQuestions,
  planStatus,
  onApprove,
  onReject,
  onRegenerate,
  onAskQuestion,
  onSuggestChanges,
}: PlanActionsProps) {
  const isExecuting = planStatus === "executing";
  const approveDisabled = hasUnansweredQuestions || planStatus !== "presented";
  const reviseDisabled = isExecuting;

  return (
    <div className="space-y-2">
      {hasUnansweredQuestions && (
        <p className="text-[11px] text-yellow-400">
          Answer all questions to approve
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={approveDisabled}
          onClick={onApprove}
          className="rounded-md bg-purple-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-purple-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Approve &amp; Execute
        </button>
        <button
          type="button"
          disabled={reviseDisabled}
          onClick={onRegenerate}
          className="rounded-md border border-sky-500/40 bg-sky-500/10 px-3 py-1.5 text-xs font-medium text-sky-100 transition-colors hover:bg-sky-500/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Regenerate Plan
        </button>
        <button
          type="button"
          disabled={reviseDisabled}
          onClick={onAskQuestion}
          className="rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          Ask a Question
        </button>
        <button
          type="button"
          disabled={reviseDisabled}
          onClick={onSuggestChanges}
          className="rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          Suggest Changes
        </button>
        <button
          type="button"
          disabled={reviseDisabled}
          onClick={onReject}
          className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-100 transition-colors hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Reject Plan
        </button>
      </div>
    </div>
  );
}
