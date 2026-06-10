import type { TaskCompleted } from "@pathfinder/shared";

export function DataTaskCompleted({ data }: { data: TaskCompleted }) {
  const isSuccess = data.status === "success";
  return (
    <div
      data-testid="data-task-completed"
      className={`my-2 rounded-md border px-3 py-2 text-xs ${
        isSuccess
          ? "border-success/30 bg-success/10"
          : "border-destructive/30 bg-destructive/10"
      }`}
    >
      <div className="flex items-center gap-2">
        <span
          className={`inline-block size-1.5 rounded-full ${
            isSuccess ? "bg-success" : "bg-destructive"
          }`}
        />
        <span className="font-medium">Task {isSuccess ? "completed" : "failed"}</span>
      </div>
      {data.error != null && data.error.length > 0 ? (
        <p className="mt-1 text-destructive">{data.error}</p>
      ) : null}
    </div>
  );
}
