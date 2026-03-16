"use client";

import { Input } from "@/lib/components/ui/Input";
import { Label } from "@/lib/components/ui/Label";

type StepNameFieldsProps = {
  oldName: string;
  name: string;
  onNameChange: (nextValue: string) => void;
};

export function StepNameFields({ oldName, name, onNameChange }: StepNameFieldsProps) {
  return (
    <div className="space-y-2">
      <div>
        <Label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Old name
        </Label>
        <Input
          type="text"
          value={oldName}
          disabled
          className="bg-muted text-muted-foreground"
        />
      </div>
      <div>
        <Label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          New name
        </Label>
        <Input
          type="text"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          className="bg-card"
        />
      </div>
    </div>
  );
}
