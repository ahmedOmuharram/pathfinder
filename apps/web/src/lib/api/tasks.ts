import type {
  TaskListResponse,
  TaskStatusResponse,
} from "@pathfinder/shared";
import { taskListResponseSchema } from "@pathfinder/shared/generated/zod/taskListResponseSchema";
import { taskStatusResponseSchema } from "@pathfinder/shared/generated/zod/taskStatusResponseSchema";
import { queryOptions } from "@tanstack/react-query";

import { requestJson } from "./http";

export type TaskStatus = TaskStatusResponse;
export type TaskList = TaskListResponse;

const ACTIVE_TASK_STATUSES = new Set([
  "pending",
  "running",
  "resuming",
]);

export async function getTaskStatus(
  conversationId: string,
  taskId: string,
): Promise<TaskStatus> {
  return await requestJson(
    taskStatusResponseSchema,
    `/api/v1/conversations/${conversationId}/tasks/${taskId}`,
  );
}

export function taskStatusOptions(conversationId: string, taskId: string) {
  return queryOptions({
    queryKey: ["conversations", conversationId, "tasks", taskId] as const,
    queryFn: () => getTaskStatus(conversationId, taskId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "complete" || status === "failed" || status === "cancelled") {
        return false;
      }
      return 5_000;
    },
  });
}

export async function listTasks(conversationId: string): Promise<TaskList> {
  return await requestJson(
    taskListResponseSchema,
    `/api/v1/conversations/${conversationId}/tasks`,
  );
}

export function tasksListOptions(conversationId: string) {
  return queryOptions({
    queryKey: ["conversations", conversationId, "tasks"] as const,
    queryFn: () => listTasks(conversationId),
    refetchInterval: (query) => {
      const tasks = query.state.data?.tasks ?? [];
      const hasActive = tasks.some((t) => ACTIVE_TASK_STATUSES.has(t.status));
      return hasActive ? 3_000 : false;
    },
  });
}
