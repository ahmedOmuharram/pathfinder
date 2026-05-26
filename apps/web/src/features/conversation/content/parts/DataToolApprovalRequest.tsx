import type { DataToolApprovalRequestPayload } from "@pathfinder/shared";

export function DataToolApprovalRequest({
  data,
}: {
  data: DataToolApprovalRequestPayload;
}) {
  return (
    <div
      data-testid="data-tool-approval-request"
      className="my-2 rounded-md border border-yellow-200 bg-yellow-50 px-3 py-2 text-xs dark:border-yellow-800 dark:bg-yellow-950"
    >
      <div className="flex items-center gap-2">
        <span className="inline-block size-1.5 rounded-full bg-yellow-500" />
        <span className="font-medium">Approval required</span>
      </div>
      <p className="mt-1 text-muted-foreground">
        <span className="font-mono">{data.toolName}</span> wants to execute
      </p>
    </div>
  );
}
