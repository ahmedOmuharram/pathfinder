import React from "react";
import ReactFlow, {
  Background,
  Controls,
  Edge,
  EdgeChange,
  type Connection,
  Node,
  NodeChange,
  type ReactFlowInstance,
  SelectionMode,
} from "reactflow";
import type { StrategyStep } from "@/types/strategy";
import { GraphToolbar } from "@/features/strategy/graph/components/GraphToolbar";
import { GraphWdkBadge } from "@/features/strategy/graph/components/GraphWdkBadge";
import { StrategyGraphActionButtons } from "@/features/strategy/graph/components/StrategyGraphActionButtons";
import { StrategyGraphDetailsHeader } from "@/features/strategy/graph/components/StrategyGraphDetailsHeader";

interface StrategyGraphLayoutProps {
  isCompact: boolean;
  detailsCollapsed: boolean;
  onToggleCollapsed: () => void;
  nameValue: string;
  onNameChange: (value: string) => void;
  onNameCommit: () => void;
  descriptionValue: string;
  onDescriptionChange: (value: string) => void;
  onDescriptionCommit: () => void;
  wdkStrategyId?: number;
  wdkUrl?: string | null;
  wdkUrlFallback?: string | null;
  interactionMode: "select" | "pan";
  onSetInteractionMode: (mode: "select" | "pan") => void;
  onRelayout: () => void;
  onAddSelectionToChat: () => void;
  canAddSelectionToChat: boolean;
  showPush: boolean;
  onPush: () => void;
  canPush: boolean;
  isPushing: boolean;
  pushLabel: string;
  pushDisabledReason?: string;
  canSave: boolean;
  onSave: () => void;
  isSaving: boolean;
  isUnsaved: boolean;
  nodes: Node[];
  edges: Edge[];
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onNodesDelete: (nodes: Node[]) => void;
  onNodeDragStop: () => void;
  onConnect: (connection: Connection) => void;
  nodeTypes: Record<string, React.ComponentType<any>>;
  onInit: (instance: ReactFlowInstance) => void;
  onMoveStart: () => void;
  selectionOnDrag: boolean;
  onSelectionChange: (nodes: Node[]) => void;
  panOnDrag: boolean;
  onNodeClick?: (node: StrategyStep) => void;
  fitViewOptions: { padding: number };
  snapGrid: [number, number];
}

export function StrategyGraphLayout(props: StrategyGraphLayoutProps) {
  const {
    isCompact,
    detailsCollapsed,
    onToggleCollapsed,
    nameValue,
    onNameChange,
    onNameCommit,
    descriptionValue,
    onDescriptionChange,
    onDescriptionCommit,
    wdkStrategyId,
    wdkUrl,
    wdkUrlFallback,
    interactionMode,
    onSetInteractionMode,
    onRelayout,
    onAddSelectionToChat,
    canAddSelectionToChat,
    showPush,
    onPush,
    canPush,
    isPushing,
    pushLabel,
    pushDisabledReason,
    canSave,
    onSave,
    isSaving,
    isUnsaved,
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onNodesDelete,
    onNodeDragStop,
    onConnect,
    nodeTypes,
    onInit,
    onMoveStart,
    selectionOnDrag,
    onSelectionChange,
    panOnDrag,
    onNodeClick,
    fitViewOptions,
    snapGrid,
  } = props;

  return (
    <div className="flex h-full w-full flex-col">
      {!isCompact && (
        <StrategyGraphDetailsHeader
          detailsCollapsed={detailsCollapsed}
          onToggleCollapsed={onToggleCollapsed}
          nameValue={nameValue}
          onNameChange={onNameChange}
          onNameCommit={onNameCommit}
          descriptionValue={descriptionValue}
          onDescriptionChange={onDescriptionChange}
          onDescriptionCommit={onDescriptionCommit}
        />
      )}
      <div className="relative flex-1">
        <GraphWdkBadge
          isCompact={isCompact}
          wdkStrategyId={wdkStrategyId}
          wdkUrl={wdkUrl}
          wdkUrlFallback={wdkUrlFallback}
        />
        <GraphToolbar
          isCompact={isCompact}
          interactionMode={interactionMode}
          onRelayout={onRelayout}
          onSetInteractionMode={onSetInteractionMode}
          onAddSelectionToChat={onAddSelectionToChat}
          canAddSelectionToChat={canAddSelectionToChat}
        />
        {!isCompact && (
          <StrategyGraphActionButtons
            showPush={showPush}
            onPush={onPush}
            canPush={canPush}
            isPushing={isPushing}
            pushLabel={pushLabel}
            pushDisabledReason={pushDisabledReason}
            canSave={canSave}
            onSave={onSave}
            isSaving={isSaving}
            isUnsaved={isUnsaved}
          />
        )}
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodesDelete={onNodesDelete}
          onNodeDragStop={onNodeDragStop}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          defaultEdgeOptions={{ type: "step" }}
          onInit={onInit}
          onMoveStart={onMoveStart}
          selectionOnDrag={selectionOnDrag}
          selectionMode={SelectionMode.Partial}
          onSelectionChange={({ nodes: selectedNodes }) => onSelectionChange(selectedNodes)}
          panOnDrag={panOnDrag}
          onNodeClick={
            isCompact || !onNodeClick
              ? undefined
              : (_, node) => {
                  const step = node.data?.step as StrategyStep | undefined;
                  if (step) {
                    onNodeClick(step);
                  }
                }
          }
          fitView
          fitViewOptions={fitViewOptions}
          snapToGrid
          snapGrid={snapGrid}
          minZoom={0.1}
          maxZoom={2}
          className="bg-slate-50"
        >
          <Background color="#e2e8f0" gap={28} size={1} />
          {!isCompact && (
            <Controls className="bg-white border-slate-200 text-slate-600" />
          )}
        </ReactFlow>
      </div>
    </div>
  );
}
