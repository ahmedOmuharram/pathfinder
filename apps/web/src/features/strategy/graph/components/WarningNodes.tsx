import { AlertTriangle } from "lucide-react";
import type { NodeProps } from "reactflow";

type WarningNodeData = { message: string };

export function WarningGroupNode({ data }: NodeProps<WarningNodeData>) {
  return (
    <div className="h-full w-full">
      <div
        className="absolute -left-2 -top-2 flex h-6 w-6 items-center justify-center rounded-full bg-amber-100 text-amber-700 shadow-sm"
        title={data.message}
        aria-label={data.message}
      >
        <AlertTriangle className="h-4 w-4" />
      </div>
    </div>
  );
}

export function WarningIconNode({ data }: NodeProps<WarningNodeData>) {
  return (
    <div
      className="group relative flex h-6 w-6 items-center justify-center rounded-full bg-amber-100 text-amber-700 shadow-sm"
      aria-label={data.message}
    >
      <AlertTriangle className="h-4 w-4" />
      <div className="pointer-events-none absolute left-6 top-0 z-50 ml-2 whitespace-nowrap rounded-md border border-amber-200 bg-white px-2 py-1 text-xs font-medium text-amber-700 opacity-0 shadow-sm transition group-hover:opacity-100">
        {data.message}
      </div>
    </div>
  );
}
