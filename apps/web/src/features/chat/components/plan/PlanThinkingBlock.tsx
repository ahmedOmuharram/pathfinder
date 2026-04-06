"use client";

interface PlanThinkingBlockProps {
  thoughts: string[];
  isLive: boolean;
}

export function PlanThinkingBlock({ thoughts, isLive }: PlanThinkingBlockProps) {
  if (thoughts.length === 0) return null;

  const combined = thoughts.join("\n\n");

  return (
    <details open={isLive} className="mb-3">
      <summary className="flex cursor-pointer items-center gap-2 text-sm font-semibold text-purple-400 select-none">
        <span className="text-xs transition-transform [[open]>&]:rotate-90">&#9654;</span>
        Strategy Thinking
        <span className="ml-auto text-xs font-normal text-muted-foreground">
          {thoughts.length} {thoughts.length === 1 ? "block" : "blocks"}
        </span>
      </summary>
      <div className="mt-2 border-l-2 border-purple-500/40 pl-3">
        <pre className="whitespace-pre-wrap text-xs leading-relaxed text-muted-foreground">
          {combined}
        </pre>
      </div>
    </details>
  );
}
