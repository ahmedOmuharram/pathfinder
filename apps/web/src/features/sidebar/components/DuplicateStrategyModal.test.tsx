// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { Strategy } from "@pathfinder/shared";

import type { DuplicateModalState } from "@/features/sidebar/utils/duplicateModalState";
import { DuplicateStrategyModal } from "./DuplicateStrategyModal";

const STRATEGY: Strategy = {
  id: "strat_1",
  name: "My pipeline",
  siteId: "plasmodb",
  isSaved: false,
  stepCount: 3,
  graph: { rootStepId: "step_1", stepTree: { stepId: 1 }, steps: {} },
} as unknown as Strategy;

function makeState(overrides: Partial<DuplicateModalState> = {}): DuplicateModalState {
  return {
    item: STRATEGY,
    name: "My pipeline",
    description: "",
    isLoading: false,
    isSubmitting: false,
    error: null,
    ...overrides,
  };
}

afterEach(() => cleanup());

describe("DuplicateStrategyModal", () => {
  it("does not render when state is null", () => {
    render(
      <DuplicateStrategyModal
        duplicateModal={null}
        setDuplicateModal={() => {}}
        onDuplicate={() => Promise.resolve()}
      />,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders the current name in the input", () => {
    render(
      <DuplicateStrategyModal
        duplicateModal={makeState()}
        setDuplicateModal={() => {}}
        onDuplicate={() => Promise.resolve()}
      />,
    );
    expect(screen.getByDisplayValue("My pipeline")).toBeInTheDocument();
  });

  it("calls setDuplicateModal when the user edits the name", () => {
    const setDuplicateModal = vi.fn();
    render(
      <DuplicateStrategyModal
        duplicateModal={makeState()}
        setDuplicateModal={setDuplicateModal}
        onDuplicate={() => Promise.resolve()}
      />,
    );
    fireEvent.change(screen.getByDisplayValue("My pipeline"), {
      target: { value: "Renamed pipeline" },
    });
    expect(setDuplicateModal).toHaveBeenCalledTimes(1);
  });

  it("disables inputs and shows loading text while loading", () => {
    render(
      <DuplicateStrategyModal
        duplicateModal={makeState({ isLoading: true })}
        setDuplicateModal={() => {}}
        onDuplicate={() => Promise.resolve()}
      />,
    );
    expect(screen.getByDisplayValue("My pipeline")).toBeDisabled();
    expect(screen.getByText(/loading strategy details/i)).toBeInTheDocument();
  });

  it("displays an error string when state.error is set", () => {
    render(
      <DuplicateStrategyModal
        duplicateModal={makeState({ error: "something went wrong" })}
        setDuplicateModal={() => {}}
        onDuplicate={() => Promise.resolve()}
      />,
    );
    expect(screen.getByText("something went wrong")).toBeInTheDocument();
  });

  it("validates name and surfaces error without calling onDuplicate when name is blank", () => {
    const setDuplicateModal = vi.fn();
    const onDuplicate = vi.fn().mockResolvedValue(undefined);
    render(
      <DuplicateStrategyModal
        duplicateModal={makeState({ name: "   " })}
        setDuplicateModal={setDuplicateModal}
        onDuplicate={onDuplicate}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /^duplicate$/i }));
    expect(onDuplicate).not.toHaveBeenCalled();
    // setDuplicateModal called with a state-update callback that returns the error
    expect(setDuplicateModal).toHaveBeenCalled();
  });

  it("calls onDuplicate with trimmed name and description on submit", async () => {
    const setDuplicateModal = vi.fn();
    const onDuplicate = vi.fn().mockResolvedValue(undefined);
    render(
      <DuplicateStrategyModal
        duplicateModal={makeState({
          name: "  New strategy  ",
          description: "  some details  ",
        })}
        setDuplicateModal={setDuplicateModal}
        onDuplicate={onDuplicate}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /^duplicate$/i }));
    await waitFor(() => {
      expect(onDuplicate).toHaveBeenCalledWith(
        "strat_1",
        "New strategy",
        "some details",
      );
    });
  });

  it("calls setDuplicateModal(null) when Cancel is clicked", () => {
    const setDuplicateModal = vi.fn();
    render(
      <DuplicateStrategyModal
        duplicateModal={makeState()}
        setDuplicateModal={setDuplicateModal}
        onDuplicate={() => Promise.resolve()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(setDuplicateModal).toHaveBeenCalledWith(null);
  });
});
