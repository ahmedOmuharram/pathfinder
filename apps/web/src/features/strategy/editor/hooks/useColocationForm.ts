import { useForm } from "@tanstack/react-form";
import type { ColocationFormValues } from "../schema/colocationSchema";
import { DEFAULT_COLOCATION } from "../components/ColocationEditor";

export function useColocationForm(initialValues?: Partial<ColocationFormValues>) {
  const defaults: ColocationFormValues = { ...DEFAULT_COLOCATION, ...initialValues };
  return useForm({
    defaultValues: defaults,
    onSubmit: () => {},
  });
}

export type ColocationForm = ReturnType<typeof useColocationForm>;
