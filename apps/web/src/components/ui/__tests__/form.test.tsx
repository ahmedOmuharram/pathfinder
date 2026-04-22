/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { useForm } from "@tanstack/react-form";

import { Input } from "@/components/ui/input";
import {
  Form,
  FormControl,
  FormDescription,
  FormError,
  FormField,
  FormItem,
  FormLabel,
} from "@/components/ui/form";

interface Submitted {
  searchName: string;
}

function Harness({ onSubmit }: { onSubmit: (v: Submitted) => void }) {
  const form = useForm({
    defaultValues: { searchName: "" } as Submitted,
    onSubmit: ({ value }) => {
      onSubmit(value);
    },
  });

  return (
    <Form form={form}>
      <FormField
        form={form}
        name="searchName"
        validators={{
          onChange: ({ value }: { value: string }) =>
            value.length === 0 ? "Required" : undefined,
        }}
      >
        {(field) => (
          <FormItem>
            <FormLabel htmlFor={field.name}>Search name</FormLabel>
            <FormControl>
              <Input
                id={field.name}
                name={field.name}
                value={field.state.value}
                onChange={(e) => {
                  field.handleChange(e.target.value);
                }}
                onBlur={field.handleBlur}
              />
            </FormControl>
            <FormDescription>Pick from the available searches</FormDescription>
            <FormError>{field.state.meta.errors[0] as string | undefined}</FormError>
          </FormItem>
        )}
      </FormField>
      <button type="submit">Submit</button>
    </Form>
  );
}

describe("Form", () => {
  it("renders label, control, description, and error slots", () => {
    render(<Harness onSubmit={() => undefined} />);

    expect(screen.getByText("Search name")).toBeInTheDocument();
    expect(
      screen.getByText("Pick from the available searches"),
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  it("shows the validation error after a change makes the field invalid", async () => {
    const user = userEvent.setup();
    render(<Harness onSubmit={() => undefined} />);

    const input = screen.getByRole("textbox");
    await user.type(input, "x");
    await user.clear(input);

    expect(await screen.findByText("Required")).toBeInTheDocument();
  });

  it("submits the form with current values", async () => {
    const user = userEvent.setup();
    let captured: Submitted | null = null;
    render(
      <Harness
        onSubmit={(v) => {
          captured = v;
        }}
      />,
    );

    await user.type(screen.getByRole("textbox"), "BlastSearch");
    await user.click(screen.getByRole("button", { name: "Submit" }));

    expect(captured).toEqual({ searchName: "BlastSearch" });
  });
});
