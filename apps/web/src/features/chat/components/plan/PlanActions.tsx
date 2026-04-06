"use client";

interface PlanActionsProps {
  hasUnansweredQuestions: boolean;
  planStatus: string;
  onApprove: () => void;
  onAskQuestion: () => void;
  onSuggestChanges: () => void;
}

export function PlanActions({
  hasUnansweredQuestions,
  planStatus,
  onApprove,
  onAskQuestion,
  onSuggestChanges,
}: PlanActionsProps) {
  const isTerminal = planStatus === "approved" || planStatus === "executing" || planStatus === "complete" || planStatus === "failed";
  const approveDisabled = hasUnansweredQuestions || isTerminal;

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
          onClick={onAskQuestion}
          className="rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent"
        >
          Ask a Question
        </button>
        <button
          type="button"
          onClick={onSuggestChanges}
          className="rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent"
        >
          Suggest Changes
        </button>
      </div>
    </div>
  );
}
