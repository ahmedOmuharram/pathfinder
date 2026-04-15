"use client";

import { useState } from "react";
import { Activity } from "lucide-react";

import { useTaskStore, type TaskRecord } from "@/state/useTaskStore";

function selectRunning(tasks: Record<string, TaskRecord>): TaskRecord[] {
  const running: TaskRecord[] = [];
  for (const key of Object.keys(tasks).sort()) {
    const task = tasks[key];
    if (task?.status === "running") running.push(task);
  }
  return running;
}

export function TaskListBadge() {
  const tasks = useTaskStore((s) => s.tasks);
  const [open, setOpen] = useState(false);
  const running = selectRunning(tasks);

  if (running.length === 0) return null;

  const label = `${running.length.toString()} task${running.length === 1 ? "" : "s"} running`;

  return (
    <div className="relative" data-testid="task-list-badge">
      <button
        type="button"
        onClick={() => {
          setOpen((v) => !v);
        }}
        className="inline-flex items-center gap-1 rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100"
        data-running-count={running.length}
        aria-expanded={open}
      >
        <Activity className="size-3" aria-hidden="true" />
        {label}
      </button>
      {open && (
        <div
          className="absolute right-0 top-full z-10 mt-1 w-64 rounded-md border border-border bg-popover p-2 shadow"
          data-testid="task-list-dropdown"
        >
          <ul className="flex flex-col gap-1">
            {running.map((task) => {
              const percent = Math.round(
                (task.lastProgress?.percent ?? 0) * 100,
              );
              return (
                <li
                  key={task.taskId}
                  className="flex flex-col rounded border border-border bg-background p-2"
                  data-task-id={task.taskId}
                >
                  <div className="flex justify-between text-xs">
                    <span className="font-medium">{task.toolName}</span>
                    <span className="text-muted-foreground">{percent}%</span>
                  </div>
                  {task.lastProgress && (
                    <div className="mt-1 text-xs text-muted-foreground">
                      {task.lastProgress.message}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
