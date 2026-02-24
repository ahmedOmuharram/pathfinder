import {
  GitFork,
  GitMerge,
  Hand,
  LayoutGrid,
  MessageSquarePlus,
  MousePointer2,
} from "lucide-react";

export function GraphToolbar(props: {
  isCompact: boolean;
  interactionMode: "select" | "pan";
  onRelayout: () => void;
  onSetInteractionMode: (mode: "select" | "pan") => void;
  onAddSelectionToChat: () => void;
  canAddSelectionToChat: boolean;
  selectedCount: number;
  onStartCombine?: () => void;
  onStartOrthologTransform?: () => void;
}) {
  const {
    isCompact,
    interactionMode,
    onRelayout,
    onSetInteractionMode,
    onAddSelectionToChat,
    canAddSelectionToChat,
    selectedCount,
    onStartCombine,
    onStartOrthologTransform,
  } = props;

  if (isCompact) return null;

  const canCombine = selectedCount === 2 && !!onStartCombine;
  const canOrtholog = selectedCount === 1 && !!onStartOrthologTransform;

  return (
    <div className="pointer-events-auto absolute right-4 top-4 z-10 flex flex-col gap-2">
      <div className="flex items-center justify-end gap-2 rounded-xl border border-border bg-card/90 p-2 shadow-sm backdrop-blur">
        <button
          type="button"
          onClick={onRelayout}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors duration-150 hover:border-input hover:text-foreground"
          title="Rearrange"
          aria-label="Rearrange graph layout"
        >
          <LayoutGrid className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => onSetInteractionMode("select")}
          className={`inline-flex h-9 w-9 items-center justify-center rounded-lg border transition-colors duration-150 ${
            interactionMode === "select"
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border text-muted-foreground hover:border-input hover:text-foreground"
          }`}
          title="Box select"
          aria-label="Box select mode"
          aria-pressed={interactionMode === "select"}
        >
          <MousePointer2 className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => onSetInteractionMode("pan")}
          className={`inline-flex h-9 w-9 items-center justify-center rounded-lg border transition-colors duration-150 ${
            interactionMode === "pan"
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border text-muted-foreground hover:border-input hover:text-foreground"
          }`}
          title="Pan mode"
          aria-label="Pan mode"
          aria-pressed={interactionMode === "pan"}
        >
          <Hand className="h-4 w-4" />
        </button>

        <div className="mx-0.5 h-5 w-px bg-border" aria-hidden="true" />

        <button
          type="button"
          onClick={onAddSelectionToChat}
          disabled={!canAddSelectionToChat}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors duration-150 hover:border-input hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
          title={
            canAddSelectionToChat
              ? "Add selection to chat"
              : "Select nodes first to add to chat"
          }
          aria-label="Add selection to chat"
        >
          <MessageSquarePlus className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={canOrtholog ? onStartOrthologTransform : undefined}
          disabled={!canOrtholog}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors duration-150 hover:border-input hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
          title={
            canOrtholog
              ? "Insert ortholog transform"
              : "Select exactly 1 step to insert an ortholog transform"
          }
          aria-label="Insert ortholog transform"
        >
          <GitFork className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={canCombine ? onStartCombine : undefined}
          disabled={!canCombine}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors duration-150 hover:border-input hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
          title={
            canCombine ? "Combine selected steps" : "Select exactly 2 steps to combine"
          }
          aria-label="Combine selected steps"
        >
          <GitMerge className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
