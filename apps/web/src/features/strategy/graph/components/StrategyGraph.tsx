"use client";

/**
 * Full editable strategy graph with drag, edge editing, combine/ortholog
 * modals, step editing, save/undo, and multi-select.
 *
 * A simpler read-only variant exists at
 * `features/experiments/components/ResultsDashboard/shared/StrategyGraph.tsx`
 * for displaying an experiment's final strategy. The two share ReactFlow and
 * the `StepNode` component but differ significantly in interaction model and
 * state management, so they are kept separate.
 */
import { useCallback, useMemo, useState } from "react";
import { CombineOperator, type StrategyWithMeta } from "@pathfinder/shared";
import type { NodeTypes } from "reactflow";
import "reactflow/dist/style.css";
import { StepNode } from "@/features/strategy/graph/components/StepNode";
import { StepEditor } from "@/features/strategy/editor/StepEditor";
import {
  WarningGroupNode,
  WarningIconNode,
} from "@/features/strategy/graph/components/WarningNodes";
import { X } from "lucide-react";
import { EmptyGraphState } from "@/features/strategy/graph/components/EmptyGraphState";
import { CombineStepModal } from "@/features/strategy/graph/components/CombineStepModal";
import { EdgeContextMenu } from "@/features/strategy/graph/components/EdgeContextMenu";
import { StrategyGraphLayout } from "@/features/strategy/graph/components/StrategyGraphLayout";
import { OrthologTransformModal } from "@/features/strategy/graph/components/OrthologTransformModal";
import {
  useStrategyGraph,
  COMBINE_OPERATORS,
} from "@/features/strategy/graph/hooks/useStrategyGraph";

interface StrategyGraphProps {
  strategy: StrategyWithMeta | null;
  siteId: string;
  onReset?: () => void;
  onToast?: (toast: {
    type: "success" | "error" | "warning" | "info";
    message: string;
  }) => void;
  variant?: "full" | "compact";
  onSwitchToChat?: () => void;
}

const NODE_TYPES: NodeTypes = {
  step: StepNode,
  warningGroup: WarningGroupNode,
  warningIcon: WarningIconNode,
};
const FIT_VIEW_OPTIONS = { padding: 0.3 } as const;
const SNAP_GRID: [number, number] = [28, 28];

export function StrategyGraph(props: StrategyGraphProps) {
  const { strategy, siteId, onToast, variant = "full", onSwitchToChat } = props;
  const nodeTypes = useMemo(() => NODE_TYPES, []);

  const g = useStrategyGraph({ strategy, siteId, onToast, variant });

  const HINTS_KEY = "pathfinder:graph-hints-dismissed";
  const [hintsDismissed, setHintsDismissed] = useState(() =>
    typeof window !== "undefined" ? !!localStorage.getItem(HINTS_KEY) : true,
  );
  const showHints =
    variant !== "compact" && !!strategy && strategy.steps.length > 0 && !hintsDismissed;

  const dismissHints = useCallback(() => {
    setHintsDismissed(true);
    localStorage.setItem(HINTS_KEY, "1");
  }, []);

  if (!strategy || strategy.steps.length === 0) {
    return <EmptyGraphState isCompact={g.isCompact} onSwitchToChat={onSwitchToChat} />;
  }

  return (
    <div className="relative flex h-full w-full flex-col">
      {showHints && (
        <div className="absolute left-3 top-3 z-10 max-w-xs rounded-md border border-border bg-card p-3 text-sm shadow-md animate-fade-in">
          <div className="flex items-start justify-between gap-2">
            <p className="font-medium text-foreground">Quick tips</p>
            <button
              type="button"
              onClick={dismissHints}
              aria-label="Dismiss tips"
              className="rounded p-0.5 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          <ul className="mt-1.5 space-y-1 text-xs text-muted-foreground">
            <li>Click a step node to edit its parameters</li>
            <li>Click an edge to change the combine operator</li>
            <li>Use the toolbar to switch between select and pan modes</li>
          </ul>
        </div>
      )}
      <StrategyGraphLayout
        isCompact={g.isCompact}
        detailsCollapsed={g.detailsCollapsed}
        onToggleCollapsed={g.toggleDetailsCollapsed}
        nameValue={g.nameValue}
        onNameChange={g.setNameValue}
        onNameCommit={() => void g.handleNameCommit()}
        descriptionValue={g.descriptionValue}
        onDescriptionChange={g.setDescriptionValue}
        onDescriptionCommit={() => void g.handleDescriptionCommit()}
        wdkStrategyId={strategy?.wdkStrategyId ?? undefined}
        wdkUrl={strategy?.wdkUrl}
        wdkUrlFallback={g.wdkUrlFallback}
        interactionMode={g.interactionMode}
        onSetInteractionMode={g.setInteractionMode}
        onRelayout={g.handleRelayout}
        onAddSelectionToChat={g.handleAddSelectionToChat}
        canAddSelectionToChat={g.selectedNodeIds.length > 0}
        selectedCount={g.selectedNodeIds.length}
        onStartCombine={g.handleStartCombineFromSelection}
        onStartOrthologTransform={g.handleStartOrthologTransformFromSelection}
        canSave={g.canSave}
        onSave={() => void g.handleSave()}
        onSaveDisabled={() => {
          onToast?.({
            type: "warning",
            message: g.saveDisabledReason || "Cannot save.",
          });
        }}
        saveDisabledReason={g.saveDisabledReason}
        isSaving={g.isSaving}
        isUnsaved={g.isUnsaved}
        nodes={g.nodes}
        edges={g.edges}
        onNodesChange={g.onNodesChange}
        onEdgesChange={g.onEdgesChange}
        onNodesDelete={g.handleNodesDelete}
        onNodeDragStop={g.handleNodeDragStop}
        onConnect={g.handleConnect}
        isValidConnection={g.isValidConnection}
        nodeTypes={nodeTypes}
        onInit={g.handleInit}
        onMoveStart={g.handleMoveStart}
        onPaneClick={() => g.setEdgeMenu(null)}
        onEdgeClick={
          g.isCompact
            ? undefined
            : (event, edge) => {
                event.stopPropagation();
                g.setEdgeMenu({ edge, x: event.clientX, y: event.clientY });
              }
        }
        selectionOnDrag={!g.isCompact && g.interactionMode === "select"}
        onSelectionChange={g.handleSelectionChange}
        panOnDrag={g.interactionMode === "pan"}
        onNodeClick={(step) => g.setSelectedStep(step)}
        fitViewOptions={FIT_VIEW_OPTIONS}
        snapGrid={SNAP_GRID}
      />
      {!g.isCompact && g.edgeMenu && (
        <EdgeContextMenu
          edge={g.edgeMenu.edge}
          x={g.edgeMenu.x}
          y={g.edgeMenu.y}
          steps={g.editableSteps}
          onDeleteEdge={(edge) => {
            g.handleDeleteEdge(edge);
            g.setEdgeMenu(null);
          }}
          onChangeOperator={(stepId, operator) => {
            g.updateStep(stepId, { operator });
            g.setEdgeMenu(null);
          }}
          onClose={() => g.setEdgeMenu(null)}
        />
      )}
      {!g.isCompact && (
        <CombineStepModal
          pendingCombine={g.pendingCombine}
          operators={COMBINE_OPERATORS}
          onChoose={(operator) =>
            void g.handleCombineCreate(operator as CombineOperator)
          }
          onCancel={g.handleCombineCancel}
        />
      )}
      {!g.isCompact && g.orthologModalOpen && g.selectedNodeIds.length === 1 && (
        <OrthologTransformModal
          open={g.orthologModalOpen}
          siteId={siteId}
          recordType={(strategy?.recordType || "gene") as string}
          onCancel={() => g.setOrthologModalOpen(false)}
          onChoose={g.handleOrthologChoose}
        />
      )}
      {!g.isCompact && g.selectedStep && (
        <StepEditor
          step={g.selectedStep}
          siteId={siteId}
          recordType={strategy?.recordType || null}
          onClose={() => g.setSelectedStep(null)}
          onUpdate={(updates) => {
            g.updateStep(g.selectedStep!.id, updates);
          }}
        />
      )}
    </div>
  );
}
