import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { stepMetaSchema, type StepMetaValues } from "../schema/stepMetaSchema";

export function useStepMetaForm(initialValues?: Partial<StepMetaValues>) {
  return useForm<StepMetaValues>({
    resolver: zodResolver(stepMetaSchema),
    defaultValues: { name: "", description: "", ...initialValues },
    mode: "onBlur",
  });
}
