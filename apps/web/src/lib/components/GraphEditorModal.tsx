import { X } from "lucide-react";
import { Modal } from "@/lib/components/Modal";
import { Button } from "@/lib/components/ui/Button";
import { StrategyGraph } from "@/features/strategy/graph/components/StrategyGraph";
import type { Strategy } from "@pathfinder/shared";

interface GraphEditorModalProps {
  open: boolean;
  onClose: () => void;
  strategy: Strategy | null;
  siteId: string;
}

export function GraphEditorModal({
  open,
  onClose,
  strategy,
  siteId,
}: GraphEditorModalProps) {
  return (
    <Modal open={open} onClose={onClose} title="Graph Editor" maxWidth="max-w-[95vw]">
      <div className="flex h-[90vh] flex-col overflow-hidden rounded-lg">
        <div className="flex items-center justify-between border-b border-border bg-muted/50 px-4 py-2.5">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Graph Editor
          </span>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-3.5 w-3.5" aria-hidden />
            Close
          </Button>
        </div>
        <div className="min-h-0 flex-1">
          <StrategyGraph strategy={strategy} siteId={siteId} />
        </div>
      </div>
    </Modal>
  );
}
