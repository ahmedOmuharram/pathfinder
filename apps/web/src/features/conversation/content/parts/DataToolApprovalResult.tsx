import type { DataToolApprovalResultPayload } from "@pathfinder/shared";

export function DataToolApprovalResult({
  data,
}: {
  data: DataToolApprovalResultPayload;
}) {
  return (
    <div
      data-testid="data-tool-approval-result"
      className={`my-1 flex items-center gap-2 text-xs ${
        data.approved
          ? "text-green-600 dark:text-green-400"
          : "text-red-600 dark:text-red-400"
      }`}
    >
      <span
        className={`inline-block size-1.5 rounded-full ${
          data.approved ? "bg-green-500" : "bg-red-500"
        }`}
      />
      <span>{data.approved ? "Approved" : "Rejected"}</span>
      {data.reason != null && data.reason.length > 0 ? (
        <span className="text-muted-foreground">— {data.reason}</span>
      ) : null}
    </div>
  );
}
