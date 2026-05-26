import type { TaskCompleted } from "@pathfinder/shared";

export function DataTaskCompleted({ data }: { data: TaskCompleted }) {
  const isSuccess = data.status === "success";
  return (
    <div
      data-testid="data-task-completed"
      className={`my-2 rounded-md border px-3 py-2 text-xs ${
        isSuccess
          ? "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950"
          : "border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950"
      }`}
    >
      <div className="flex items-center gap-2">
        <span
          className={`inline-block size-1.5 rounded-full ${
            isSuccess ? "bg-green-500" : "bg-red-500"
          }`}
        />
        <span className="font-medium">
          Task {isSuccess ? "completed" : "failed"}
        </span>
      </div>
      {data.error != null && data.error.length > 0 ? (
        <p className="mt-1 text-red-600 dark:text-red-400">{data.error}</p>
      ) : null}
    </div>
  );
}
