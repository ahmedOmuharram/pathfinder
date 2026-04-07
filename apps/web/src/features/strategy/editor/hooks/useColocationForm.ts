import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { colocationSchema, type ColocationFormValues } from "../schema/colocationSchema";
import { DEFAULT_COLOCATION } from "../components/ColocationEditor";

export function useColocationForm(initialValues?: Partial<ColocationFormValues>) {
  return useForm<ColocationFormValues>({
    resolver: zodResolver(colocationSchema),
    defaultValues: { ...DEFAULT_COLOCATION, ...initialValues },
    mode: "onBlur",
  });
}
