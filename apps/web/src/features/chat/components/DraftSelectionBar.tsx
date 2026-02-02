import { normalizeNodeSelection } from "@/features/chat/node_selection";
import { NodeCard } from "./NodeCard";

export function DraftSelectionBar(props: {
  selection: Record<string, unknown>;
  onRemove: () => void;
}) {
  const { selection, onRemove } = props;
  const normalized = normalizeNodeSelection(selection);

  return (
    <div className="mb-3 flex items-start justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
      <div className="flex w-full gap-2 overflow-x-auto pb-1">
        {normalized.nodes.map((node, idx) => (
          <div key={`draft-node-${idx}`} className="shrink-0 min-w-[220px]">
            <NodeCard node={node} />
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={onRemove}
        className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 hover:text-slate-600"
      >
        Remove
      </button>
    </div>
  );
}

