import type { ToolCallMessagePartComponent } from "@assistant-ui/react";

export const ToolThink: ToolCallMessagePartComponent<{ thought?: string }, unknown> = ({
  args,
}) => {
  const thought = (args.thought ?? "").trim();
  if (thought === "") return null;
  return (
    <div data-testid="tool-think" className="my-1 text-xs text-muted-foreground">
      <span className="font-mono text-[10px] text-muted-foreground">think</span>
      <span className="mx-1 text-muted-foreground">:</span>
      <span className="italic">{thought}</span>
    </div>
  );
};
