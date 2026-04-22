/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { VennPicker } from "./VennPicker";

afterEach(cleanup);

describe("VennPicker", () => {
  it("renders three clickable region paths", () => {
    render(<VennPicker operator="INTERSECT" onChange={() => {}} />);
    const minus = screen.getByLabelText("A only");
    const intersect = screen.getByLabelText("Intersection region");
    const rminus = screen.getByLabelText("B only");
    expect(minus).toBeTruthy();
    expect(intersect).toBeTruthy();
    expect(rminus).toBeTruthy();
  });

  it("clicking left crescent fires MINUS", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<VennPicker operator="INTERSECT" onChange={onChange} />);
    await user.click(screen.getByLabelText("A only"));
    expect(onChange).toHaveBeenCalledWith("MINUS");
  });

  it("clicking lens fires INTERSECT", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<VennPicker operator="MINUS" onChange={onChange} />);
    await user.click(screen.getByLabelText("Intersection region"));
    expect(onChange).toHaveBeenCalledWith("INTERSECT");
  });

  it("clicking right crescent fires RMINUS", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<VennPicker operator="INTERSECT" onChange={onChange} />);
    await user.click(screen.getByLabelText("B only"));
    expect(onChange).toHaveBeenCalledWith("RMINUS");
  });

  it("clicking Union preset fires UNION", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<VennPicker operator="INTERSECT" onChange={onChange} />);
    await user.click(screen.getByLabelText("Union"));
    expect(onChange).toHaveBeenCalledWith("UNION");
  });

  it("clicking Colocate preset fires COLOCATE", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<VennPicker operator="INTERSECT" onChange={onChange} />);
    await user.click(screen.getByLabelText("Colocate"));
    expect(onChange).toHaveBeenCalledWith("COLOCATE");
  });

  it("readout reflects current operator", () => {
    render(<VennPicker operator="INTERSECT" onChange={() => {}} />);
    expect(screen.getByText(/INTERSECT/)).toBeTruthy();
  });

  it("readout renders MINUS as 'A only'", () => {
    render(<VennPicker operator="MINUS" onChange={() => {}} />);
    expect(screen.getByText(/A only/i)).toBeTruthy();
  });

  it("Swap button toggles MINUS to RMINUS via onChange", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<VennPicker operator="MINUS" onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /swap/i }));
    expect(onChange).toHaveBeenCalledWith("RMINUS");
  });

  it("Swap button toggles RMINUS to MINUS via onChange", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<VennPicker operator="RMINUS" onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /swap/i }));
    expect(onChange).toHaveBeenCalledWith("MINUS");
  });

  it("Swap is no-op for INTERSECT (does not call onChange with new operator)", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<VennPicker operator="INTERSECT" onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /swap/i }));
    // Either not called, or called with same op
    if (onChange.mock.calls.length > 0) {
      const lastArg = onChange.mock.calls[onChange.mock.calls.length - 1]?.[0];
      expect(lastArg).toBe("INTERSECT");
    }
  });

  it("renders custom A/B labels in readout", () => {
    render(
      <VennPicker
        operator="MINUS"
        onChange={() => {}}
        aLabel="Step 1"
        bLabel="Step 2"
      />,
    );
    expect(screen.getByText(/Step 1/)).toBeTruthy();
  });
});
