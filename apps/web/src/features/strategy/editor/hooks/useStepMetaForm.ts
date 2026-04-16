import { useForm } from "@tanstack/react-form";
import type { StepMetaValues } from "../schema/stepMetaSchema";

export function useStepMetaForm(initialValues?: Partial<StepMetaValues>) {
  return useForm({
    defaultValues: { name: "", description: "", ...initialValues } satisfies StepMetaValues,
    onSubmit: () => {},
  });
}

export type StepMetaForm = ReturnType<typeof useStepMetaForm>;
