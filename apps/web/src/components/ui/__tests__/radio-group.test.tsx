/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";

import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

describe("RadioGroup", () => {
  it("selects item on click", async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();
    render(
      <RadioGroup onValueChange={onValueChange}>
        <RadioGroupItem value="a" aria-label="A" />
        <RadioGroupItem value="b" aria-label="B" />
      </RadioGroup>,
    );

    await user.click(screen.getByLabelText("B"));

    expect(onValueChange).toHaveBeenCalledWith("b");
  });

  it("reflects controlled value", () => {
    render(
      <RadioGroup value="a">
        <RadioGroupItem value="a" aria-label="A" />
        <RadioGroupItem value="b" aria-label="B" />
      </RadioGroup>,
    );
    expect(screen.getByLabelText("A").getAttribute("data-state")).toBe("checked");
    expect(screen.getByLabelText("B").getAttribute("data-state")).toBe("unchecked");
  });
});
