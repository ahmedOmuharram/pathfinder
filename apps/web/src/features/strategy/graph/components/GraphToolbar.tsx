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

  return (
    <div className="pointer-events-auto absolute right-4 top-4 z-10 flex flex-col gap-2">
      <div className="flex items-center justify-end gap-2 rounded-xl border border-slate-200 bg-white/90 p-2 shadow-sm backdrop-blur">
        <button
          type="button"
          onClick={onRelayout}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
          title="Rearrange"
        >
          <LayoutGrid className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => onSetInteractionMode("select")}
          className={`inline-flex h-9 w-9 items-center justify-center rounded-lg border transition ${
            interactionMode === "select"
              ? "border-slate-400 bg-slate-900 text-white"
              : "border-slate-200 text-slate-600 hover:border-slate-300 hover:text-slate-900"
          }`}
          title="Box select"
        >
          <MousePointer2 className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => onSetInteractionMode("pan")}
          className={`inline-flex h-9 w-9 items-center justify-center rounded-lg border transition ${
            interactionMode === "pan"
              ? "border-slate-400 bg-slate-900 text-white"
              : "border-slate-200 text-slate-600 hover:border-slate-300 hover:text-slate-900"
          }`}
          title="Drag"
        >
          <Hand className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onAddSelectionToChat}
          disabled={!canAddSelectionToChat}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-60"
          title="Add selection to chat"
        >
          <MessageSquarePlus className="h-4 w-4" />
        </button>

        {selectedCount === 1 && onStartOrthologTransform ? (
          <button
            type="button"
            onClick={onStartOrthologTransform}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            title="Insert ortholog transform"
          >
            <GitFork className="h-4 w-4" />
          </button>
        ) : null}

        {selectedCount === 2 && onStartCombine ? (
          <button
            type="button"
            onClick={onStartCombine}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            title="Combine selected steps"
          >
            <GitMerge className="h-4 w-4" />
          </button>
        ) : null}
      </div>
    </div>
  );
}

