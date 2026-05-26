import { useMessage, type ThreadMessage } from "@assistant-ui/react";
import type { ToolCallMessagePartComponent } from "@assistant-ui/react";

function selectLatestModel(m: ThreadMessage): string | null {
  for (let i = m.content.length - 1; i >= 0; i -= 1) {
    const part = m.content[i];
    if (part?.type !== "data") continue;
    if ("name" in part && part.name === "phase-start") {
      const data = part.data as { model?: string } | undefined;
      return data?.model ?? null;
    }
  }
  return null;
}

export const ToolThink: ToolCallMessagePartComponent<
  { thought?: string },
  unknown
> = ({ args }) => {
  const model = useMessage({ optional: true, selector: selectLatestModel });
  const thought = (args.thought ?? "").trim();
  if (thought === "") return null;
  return (
    <div
      data-testid="tool-think"
      className="my-1 text-xs text-muted-foreground"
    >
      <span className="font-mono text-[10px] text-muted-foreground/60">
        {model ?? "think"}
      </span>
      <span className="mx-1 text-muted-foreground/40">:</span>
      <span className="italic">{thought}</span>
    </div>
  );
};
