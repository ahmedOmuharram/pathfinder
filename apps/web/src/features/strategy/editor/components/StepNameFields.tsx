"use client";

type StepNameFieldsProps = {
  oldName: string;
  name: string;
  onNameChange: (nextValue: string) => void;
};

export function StepNameFields({ oldName, name, onNameChange }: StepNameFieldsProps) {
  return (
    <div className="space-y-2">
      <div>
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Old name
        </label>
        <input
          type="text"
          value={oldName}
          disabled
          className="w-full cursor-not-allowed rounded-md border border-border bg-muted px-3 py-2 text-sm text-muted-foreground"
        />
      </div>
      <div>
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          New name
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground"
        />
      </div>
    </div>
  );
}
