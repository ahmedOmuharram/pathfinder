"use client";

import { CombineOperator, CombineOperatorBadgeLabels } from "@pathfinder/shared";

interface OpBadgeProps {
  operator: string;
  size?: "sm" | "md";
}

function getOpBadgeLabel(op: string): string {
  return (CombineOperatorBadgeLabels as Record<string, string>)[op] ?? op;
}

export function VennIcon({ operator }: { operator: string }) {
  const stroke = "#64748b"; // slate-500
  const highlight = "#00e676"; // vibrant green (A400-ish)
  const bg = "#f8fafc"; // slate-50 (matches badge bg)

  // Standard venn: centers (14,12) and (22,12), r=8.
  // Intersection points are (18, 12 ± sqrt(64-16)) = (18, 12 ± 6.9282)
  // Lens boundary is one arc from each circle.
  const overlapPath = "M18 5.0718 A8 8 0 0 1 18 18.9282 A8 8 0 0 1 18 5.0718 Z";

  return (
    <svg
      width="24"
      height="16"
      viewBox="0 0 36 24"
      aria-hidden="true"
      className="mr-1.5"
    >
      {/* Highlight selected region(s) */}
      {operator === CombineOperator.UNION && (
        <>
          <circle cx="14" cy="12" r="8" fill={highlight} fillOpacity="0.35" />
          <circle cx="22" cy="12" r="8" fill={highlight} fillOpacity="0.35" />
        </>
      )}
      {operator === CombineOperator.INTERSECT && (
        <path d={overlapPath} fill={highlight} fillOpacity="0.9" />
      )}
      {(operator === CombineOperator.MINUS || operator === CombineOperator.LONLY) && (
        <>
          <circle cx="14" cy="12" r="8" fill={highlight} fillOpacity="0.5" />
          {/* Punch out the overlap so it's truly "left only" */}
          <path d={overlapPath} fill={bg} />
        </>
      )}
      {(operator === CombineOperator.RMINUS || operator === CombineOperator.RONLY) && (
        <>
          <circle cx="22" cy="12" r="8" fill={highlight} fillOpacity="0.5" />
          {/* Punch out the overlap so it's truly "right only" */}
          <path d={overlapPath} fill={bg} />
        </>
      )}
      {operator === CombineOperator.COLOCATE && (
        <>
          {/* Not a set operator; show "near" as two separated sets + distance arrow */}
          <circle cx="12" cy="12" r="7" fill={highlight} fillOpacity="0.25" />
          <circle cx="24" cy="12" r="7" fill={highlight} fillOpacity="0.25" />
          <path
            d="M16.5 12H19.5"
            stroke={highlight}
            strokeWidth="2"
            strokeLinecap="round"
          />
          <path
            d="M16.5 12l1.2-1.2M16.5 12l1.2 1.2"
            stroke={highlight}
            strokeWidth="1.6"
            strokeLinecap="round"
          />
          <path
            d="M19.5 12l-1.2-1.2M19.5 12l-1.2 1.2"
            stroke={highlight}
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </>
      )}
      {/* outlines */}
      {operator === CombineOperator.COLOCATE ? (
        <>
          <circle cx="12" cy="12" r="7" fill="none" stroke={stroke} strokeWidth="1.5" />
          <circle cx="24" cy="12" r="7" fill="none" stroke={stroke} strokeWidth="1.5" />
        </>
      ) : (
        <>
          <circle cx="14" cy="12" r="8" fill="none" stroke={stroke} strokeWidth="1.5" />
          <circle cx="22" cy="12" r="8" fill="none" stroke={stroke} strokeWidth="1.5" />
        </>
      )}
    </svg>
  );
}

export function OpBadge({ operator, size = "md" }: OpBadgeProps) {
  const label = getOpBadgeLabel(operator);

  const sizeClasses = size === "sm" ? "px-1.5 py-0.5 text-xs" : "px-2 py-1 text-xs";

  return (
    <span
      className={`inline-flex items-center rounded-md border border-border bg-muted font-mono font-semibold text-foreground ${sizeClasses}`}
    >
      <VennIcon operator={operator} />
      {label}
    </span>
  );
}
