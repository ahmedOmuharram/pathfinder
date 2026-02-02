"use client";

interface OpBadgeProps {
  operator: string;
  size?: "sm" | "md";
}

const OP_INFO: Record<string, { label: string }> = {
  INTERSECT: { label: "AND" },
  UNION: { label: "OR" },
  MINUS_LEFT: { label: "NOT" },
  MINUS_RIGHT: { label: "NOT" },
  COLOCATE: { label: "NEAR" },
};

export function OpBadge({ operator, size = "md" }: OpBadgeProps) {
  const info = OP_INFO[operator] || {
    label: operator,
  };

  const sizeClasses =
    size === "sm" ? "px-1.5 py-0.5 text-[11px]" : "px-2 py-1 text-xs";

  return (
    <span
      className={`inline-flex items-center rounded-md border border-slate-200 bg-slate-50 font-mono font-semibold text-slate-700 ${sizeClasses}`}
    >
      {info.label}
    </span>
  );
}

