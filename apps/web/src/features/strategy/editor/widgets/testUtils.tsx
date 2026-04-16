import type { ReactNode } from "react";
import { useForm } from "@tanstack/react-form";
import type { ParamWidgetProps } from "./types";

type ParamFormValues = Record<string, string | string[]>;

export function WidgetTestForm({
  name,
  defaultValue,
  children,
}: {
  name: string;
  defaultValue: string | string[];
  children: (field: ParamWidgetProps["field"]) => ReactNode;
}) {
  const form = useForm({
    defaultValues: { [name]: defaultValue } as ParamFormValues,
    onSubmit: () => {},
  });

  return (
    <form.Field name={name}>
      {(field) => children(field as unknown as ParamWidgetProps["field"])}
    </form.Field>
  );
}

export function WidgetTestFormWithValidation({
  name,
  defaultValue,
  validator,
  children,
}: {
  name: string;
  defaultValue: string | string[];
  validator: (value: string | string[]) => string | undefined;
  children: (field: ParamWidgetProps["field"]) => ReactNode;
}) {
  const form = useForm({
    defaultValues: { [name]: defaultValue } as ParamFormValues,
    onSubmit: () => {},
  });

  return (
    <form.Field
      name={name}
      validators={{ onBlur: ({ value }: { value: string | string[] }) => validator(value) }}
    >
      {(field) => children(field as unknown as ParamWidgetProps["field"])}
    </form.Field>
  );
}
