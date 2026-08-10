// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { OperationChoice } from "@/features/strategy/operations";
import { GraphActionConfirm } from "@/features/strategy/graph/components/GraphActionConfirm";
import { useGraphActionConfirm } from "./useGraphActionConfirm";

function makeChoices(): OperationChoice<"a" | "b">[] {
  return [
    {
      resolution: "a",
      title: "First",
      description: "first option",
      isDefault: true,
      willDelete: [],
    },
    {
      resolution: "b",
      title: "Second",
      description: "second option",
      isDefault: false,
      willDelete: [],
    },
  ];
}

function Harness(props: { onResolve: (r: "a" | "b") => void }) {
  const confirm = useGraphActionConfirm<"a" | "b">();
  return (
    <>
      <button
        data-testid="open"
        onClick={() =>
          confirm.confirmAction({
            title: "Pick one",
            choices: makeChoices(),
            onResolve: props.onResolve,
          })
        }
      >
        open
      </button>
      <span data-testid="open-flag">{confirm.isOpen ? "yes" : "no"}</span>
      {confirm.dialogProps !== null && <GraphActionConfirm {...confirm.dialogProps} />}
    </>
  );
}

describe("useGraphActionConfirm", () => {
  it("opens the dialog and reports isOpen", async () => {
    render(<Harness onResolve={() => {}} />);
    expect(screen.getByTestId("open-flag").textContent).toBe("no");
    await userEvent.click(screen.getByTestId("open"));
    expect(screen.getByTestId("open-flag").textContent).toBe("yes");
    expect(screen.getByText("Pick one")).toBeTruthy();
  });

  it("calls onResolve with the chosen resolution and closes", async () => {
    const onResolve = vi.fn();
    render(<Harness onResolve={onResolve} />);
    await userEvent.click(screen.getByTestId("open"));
    const radios = screen.getAllByRole("radio");
    await userEvent.click(radios[1]!);
    await userEvent.click(screen.getByTestId("graph-action-confirm-apply"));
    expect(onResolve).toHaveBeenCalledWith("b");
    expect(screen.getByTestId("open-flag").textContent).toBe("no");
  });

  it("Cancel dismisses without resolving", async () => {
    const onResolve = vi.fn();
    render(<Harness onResolve={onResolve} />);
    await userEvent.click(screen.getByTestId("open"));
    expect(screen.getByTestId("open-flag").textContent).toBe("yes");
    await userEvent.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(screen.getByTestId("open-flag").textContent).toBe("no");
    expect(onResolve).not.toHaveBeenCalled();
  });
});
