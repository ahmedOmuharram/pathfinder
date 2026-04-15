// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { useTaskStore } from "@/state/useTaskStore";

import { TaskListBadge } from "./TaskListBadge";

beforeEach(() => {
  useTaskStore.getState().reset();
});

describe("TaskListBadge", () => {
  it("renders nothing when no tasks are running", () => {
    const { container } = render(<TaskListBadge />);
    expect(container.textContent).toBe("");
  });

  it("does not render when all tasks have completed", () => {
    useTaskStore.getState().startTask({
      taskId: "t1",
      toolName: "x",
      startedAt: new Date().toISOString(),
      estimatedDurationSeconds: 30,
    });
    useTaskStore.getState().completeTask("t1", "success");
    const { container } = render(<TaskListBadge />);
    expect(container.textContent).toBe("");
  });

  it("shows a badge with the running task count", () => {
    useTaskStore.getState().startTask({
      taskId: "t1",
      toolName: "x",
      startedAt: new Date().toISOString(),
      estimatedDurationSeconds: 30,
    });
    useTaskStore.getState().startTask({
      taskId: "t2",
      toolName: "y",
      startedAt: new Date().toISOString(),
      estimatedDurationSeconds: 60,
    });
    render(<TaskListBadge />);
    const badge = screen.getByTestId("task-list-badge");
    expect(badge).toHaveTextContent(/2 tasks running/);
    expect(
      badge.querySelector("[data-running-count]")?.getAttribute(
        "data-running-count",
      ),
    ).toBe("2");
  });

  it("singular label when only one task is running", () => {
    useTaskStore.getState().startTask({
      taskId: "t1",
      toolName: "x",
      startedAt: new Date().toISOString(),
      estimatedDurationSeconds: 30,
    });
    render(<TaskListBadge />);
    expect(screen.getByRole("button")).toHaveTextContent(/1 task running/);
  });

  it("clicking the badge opens a dropdown listing active tasks", () => {
    useTaskStore.getState().startTask({
      taskId: "t1",
      toolName: "run_control_tests",
      startedAt: new Date().toISOString(),
      estimatedDurationSeconds: 30,
    });
    useTaskStore
      .getState()
      .setProgress("t1", { percent: 0.4, message: "step 2/5" });
    render(<TaskListBadge />);
    expect(screen.queryByTestId("task-list-dropdown")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button"));
    const dropdown = screen.getByTestId("task-list-dropdown");
    expect(dropdown).toHaveTextContent(/run_control_tests/);
    expect(dropdown).toHaveTextContent(/40%/);
    expect(dropdown).toHaveTextContent(/step 2\/5/);
  });

  it("clicking the badge again closes the dropdown", () => {
    useTaskStore.getState().startTask({
      taskId: "t1",
      toolName: "x",
      startedAt: new Date().toISOString(),
      estimatedDurationSeconds: 30,
    });
    render(<TaskListBadge />);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByTestId("task-list-dropdown")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button"));
    expect(screen.queryByTestId("task-list-dropdown")).not.toBeInTheDocument();
  });
});
