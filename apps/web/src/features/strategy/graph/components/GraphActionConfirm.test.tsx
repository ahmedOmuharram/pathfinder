// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { OperationChoice } from "@/features/strategy/operations";
import { GraphActionConfirm } from "./GraphActionConfirm";

function makeChoices(): OperationChoice<"a" | "b" | "c">[] {
  return [
    {
      resolution: "a",
      title: "Choice A",
      description: "first",
      isDefault: true,
      willDelete: ["x"],
    },
    {
      resolution: "b",
      title: "Choice B",
      description: "second",
      isDefault: false,
      willDelete: ["x", "y"],
    },
    {
      resolution: "c",
      title: "Choice C",
      description: "third",
      isDefault: false,
      willDelete: [],
    },
  ];
}

describe("GraphActionConfirm", () => {
  it("renders all choices and surfaces how many steps each removes", () => {
    render(
      <GraphActionConfirm
        open
        onOpenChange={() => {}}
        title="Delete this step?"
        choices={makeChoices()}
        onConfirm={() => {}}
      />,
    );
    expect(screen.getByText("Choice A")).toBeVisible();
    expect(screen.getByText("Choice B")).toBeVisible();
    expect(
      screen.getAllByText(/Will delete \d+/).map((el) => el.textContent.trim()),
    ).toEqual(["Will delete 1", "Will delete 2", "Will delete 0"]);
  });

  it("preselects the default choice", () => {
    render(
      <GraphActionConfirm
        open
        onOpenChange={() => {}}
        title="Delete this step?"
        choices={makeChoices()}
        onConfirm={() => {}}
      />,
    );
    const radios = screen.getAllByRole("radio");
    const labels = ["Choice A", "Choice B", "Choice C"];
    radios.forEach((r, i) => {
      const expected = labels[i] === "Choice A" ? "true" : "false";
      expect(r.getAttribute("aria-checked")).toBe(expected);
    });
  });

  it("calls onConfirm with the chosen resolution and closes", async () => {
    const onConfirm = vi.fn();
    const onOpenChange = vi.fn();
    render(
      <GraphActionConfirm
        open
        onOpenChange={onOpenChange}
        title="Delete?"
        choices={makeChoices()}
        onConfirm={onConfirm}
      />,
    );
    const radios = screen.getAllByRole("radio");
    await userEvent.click(radios[1]!);
    await userEvent.click(screen.getByTestId("graph-action-confirm-apply"));
    expect(onConfirm).toHaveBeenCalledWith("b");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("Cancel does not call onConfirm", async () => {
    const onConfirm = vi.fn();
    render(
      <GraphActionConfirm
        open
        onOpenChange={() => {}}
        title="Delete?"
        choices={makeChoices()}
        onConfirm={onConfirm}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
