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
        <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          Old name
        </label>
        <input
          type="text"
          value={oldName}
          disabled
          className="w-full cursor-not-allowed rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-[13px] text-slate-500"
        />
      </div>
      <div>
        <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          New name
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-[13px] text-slate-900 focus:border-slate-300 focus:outline-none focus:ring-1 focus:ring-slate-200 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500"
        />
      </div>
    </div>
  );
}
