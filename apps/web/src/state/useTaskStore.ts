import { create } from "zustand";

export interface TaskProgressSnapshot {
  percent: number;
  message: string;
  toolSpecific?: unknown;
}

export type TaskStatus = "running" | "success" | "failed";

export interface TaskRecord {
  taskId: string;
  toolName: string;
  startedAt: string;
  estimatedDurationSeconds: number;
  lastProgress: TaskProgressSnapshot | null;
  status: TaskStatus;
  error?: string;
}

export interface StartTaskPayload {
  taskId: string;
  toolName: string;
  startedAt: string;
  estimatedDurationSeconds: number;
}

export interface TaskState {
  tasks: Record<string, TaskRecord>;
  startTask: (task: StartTaskPayload) => void;
  setProgress: (taskId: string, progress: TaskProgressSnapshot) => void;
  completeTask: (taskId: string, status: "success" | "failed", error?: string) => void;
  reset: () => void;
}

export const useTaskStore = create<TaskState>((set) => ({
  tasks: {},
  startTask: (task) =>
    set((state) => ({
      tasks: {
        ...state.tasks,
        [task.taskId]: {
          taskId: task.taskId,
          toolName: task.toolName,
          startedAt: task.startedAt,
          estimatedDurationSeconds: task.estimatedDurationSeconds,
          lastProgress: null,
          status: "running",
        },
      },
    })),
  setProgress: (taskId, progress) =>
    set((state) => {
      if (!Object.hasOwn(state.tasks, taskId)) return state;
      const current = state.tasks[taskId];
      if (!current) return state;
      return {
        tasks: {
          ...state.tasks,
          [taskId]: { ...current, lastProgress: progress },
        },
      };
    }),
  completeTask: (taskId, status, error) =>
    set((state) => {
      if (!Object.hasOwn(state.tasks, taskId)) return state;
      const current = state.tasks[taskId];
      if (!current) return state;
      const next: TaskRecord =
        error === undefined ? { ...current, status } : { ...current, status, error };
      return { tasks: { ...state.tasks, [taskId]: next } };
    }),
  reset: () => set({ tasks: {} }),
}));
