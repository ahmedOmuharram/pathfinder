import type { TaskStatusResponse } from "@pathfinder/shared/generated/types/TaskStatusResponse";
import { taskStatusResponseSchema } from "@pathfinder/shared/generated/zod/taskStatusResponseSchema";
import { queryOptions } from "@tanstack/react-query";

import { requestJson } from "./http";

export type TaskStatus = TaskStatusResponse;

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
