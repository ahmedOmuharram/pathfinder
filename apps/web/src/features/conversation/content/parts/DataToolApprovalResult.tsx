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
        data.approved ? "text-success" : "text-destructive"
      }`}
    >
      <span
        className={`inline-block size-1.5 rounded-full ${
          data.approved ? "bg-success" : "bg-destructive"
        }`}
      />
      <span>{data.approved ? "Approved" : "Rejected"}</span>
      {data.reason != null && data.reason.length > 0 ? (
        <span className="text-muted-foreground">— {data.reason}</span>
      ) : null}
    </div>
  );
}
