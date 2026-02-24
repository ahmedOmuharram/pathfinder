import { buildDelegationExecutorMessage } from "@/features/chat/utils/delegationDraft";

interface DelegationDraftViewerProps {
  delegationDraft: {
    goal?: string;
    plan?: unknown;
  };
  onBuildExecutor: (message: string) => void;
}

export function DelegationDraftViewer({
  delegationDraft,
  onBuildExecutor,
}: DelegationDraftViewerProps) {
  return (
    <div className="border-b border-border bg-card px-4 py-3">
      <details
        className="rounded-lg border border-border bg-card px-3 py-2"
        data-testid="delegation-draft-details"
      >
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Delegation plan (draft)
        </summary>
        <div className="mt-2 space-y-2 text-sm text-foreground">
          {typeof delegationDraft.goal === "string" && delegationDraft.goal.trim() ? (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Goal
              </div>
              <div className="mt-1 rounded-md border border-border bg-muted p-2 text-sm text-foreground">
                {delegationDraft.goal}
              </div>
            </div>
          ) : null}
          {delegationDraft.plan ? (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Plan JSON
              </div>
              <pre className="mt-1 max-h-64 overflow-auto rounded-md border border-border bg-muted p-2 text-xs text-foreground">
                {JSON.stringify(delegationDraft.plan, null, 2)}
              </pre>
            </div>
          ) : null}
          <div className="flex justify-end">
            <button
              type="button"
              data-testid="delegation-build-executor"
              className="rounded-md border border-border bg-primary px-2 py-1 text-xs font-semibold uppercase tracking-wide text-primary-foreground transition-colors duration-150"
              onClick={() =>
                onBuildExecutor(buildDelegationExecutorMessage(delegationDraft))
              }
            >
              Build in executor
            </button>
          </div>
        </div>
      </details>
    </div>
  );
}
