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
    <div className="border-b border-slate-200 bg-white px-4 py-3">
      <details
        className="rounded-lg border border-slate-200 bg-white px-3 py-2"
        data-testid="delegation-draft-details"
      >
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-slate-500">
          Delegation plan (draft)
        </summary>
        <div className="mt-2 space-y-2 text-[12px] text-slate-700">
          {typeof delegationDraft.goal === "string" && delegationDraft.goal.trim() ? (
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Goal
              </div>
              <div className="mt-1 rounded-md border border-slate-100 bg-slate-50 p-2 text-[12px] text-slate-700">
                {delegationDraft.goal}
              </div>
            </div>
          ) : null}
          {delegationDraft.plan ? (
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Plan JSON
              </div>
              <pre className="mt-1 max-h-64 overflow-auto rounded-md border border-slate-100 bg-slate-50 p-2 text-[11px] text-slate-700">
                {JSON.stringify(delegationDraft.plan, null, 2)}
              </pre>
            </div>
          ) : null}
          <div className="flex justify-end">
            <button
              type="button"
              data-testid="delegation-build-executor"
              className="rounded-md border border-slate-200 bg-slate-900 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-white"
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
