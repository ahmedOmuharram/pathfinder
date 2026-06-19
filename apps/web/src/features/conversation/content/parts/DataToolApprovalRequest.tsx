import type { DataToolApprovalRequestPayload } from "@pathfinder/shared";

import { humanizeToolName } from "@/lib/utils/toolNames";

export function DataToolApprovalRequest({
  data,
}: {
  data: DataToolApprovalRequestPayload;
}) {
  // The plan-submit approval is owned by the inline PlanCarousel.
  if (data.toolName === "submit_plan_for_approval") return null;
  return (
    <div
      data-testid="data-tool-approval-request"
      className="my-2 rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-xs"
    >
      <div className="flex items-center gap-2">
        <span className="inline-block size-1.5 rounded-full bg-warning" />
        <span className="font-medium">Approval required</span>
      </div>
      <p className="mt-1 text-muted-foreground">
        <span className="font-medium text-foreground">
          {humanizeToolName(data.toolName)}
        </span>{" "}
        wants to execute
      </p>
    </div>
  );
}
