// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BranchOrRevertDialog } from "./BranchOrRevertDialog";

describe("BranchOrRevertDialog", () => {
  it("fires onBranch when branch clicked", async () => {
    const onBranch = vi.fn();
    render(
      <BranchOrRevertDialog
        open
        canBranch
        pending={false}
        onBranch={onBranch}
        onRevert={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByTestId("edit-branch-button"));
    expect(onBranch).toHaveBeenCalledOnce();
  });

  it("fires onRevert when revert clicked", async () => {
    const onRevert = vi.fn();
    render(
      <BranchOrRevertDialog
        open
        canBranch
        pending={false}
        onBranch={vi.fn()}
        onRevert={onRevert}
        onCancel={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByTestId("edit-revert-button"));
    expect(onRevert).toHaveBeenCalledOnce();
  });

  it("disables branch when canBranch is false", () => {
    render(
      <BranchOrRevertDialog
        open
        canBranch={false}
        pending={false}
        onBranch={vi.fn()}
        onRevert={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByTestId("edit-branch-button")).toBeDisabled();
    expect(screen.getByTestId("edit-revert-button")).toBeEnabled();
  });

  it("disables both actions while pending", () => {
    render(
      <BranchOrRevertDialog
        open
        canBranch
        pending
        onBranch={vi.fn()}
        onRevert={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByTestId("edit-branch-button")).toBeDisabled();
    expect(screen.getByTestId("edit-revert-button")).toBeDisabled();
  });
});
