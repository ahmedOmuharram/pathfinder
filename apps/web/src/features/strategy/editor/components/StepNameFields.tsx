"use client";

import { useFormContext } from "react-hook-form";
import { Input } from "@/lib/components/ui/Input";
import { Label } from "@/lib/components/ui/Label";

type StepNameFieldsProps = {
  oldName: string;
};

export function StepNameFields({ oldName }: StepNameFieldsProps) {
  const { register, formState: { errors } } = useFormContext();
  const nameError = errors["name"];

  return (
    <div className="space-y-2">
      <div>
        <Label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Old name
        </Label>
        <Input type="text" value={oldName} disabled className="bg-muted text-muted-foreground" />
      </div>
      <div>
        <Label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          New name
        </Label>
        <Input
          {...register("name")}
          type="text"
          aria-invalid={nameError ? "true" : undefined}
          aria-describedby={nameError ? "name-error" : undefined}
          className="bg-card"
        />
        {nameError?.message != null && (
          <p id="name-error" role="alert" className="mt-1 text-xs text-destructive">
            {String(nameError.message)}
          </p>
        )}
      </div>
    </div>
  );
}
