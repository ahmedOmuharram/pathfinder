import React from "react";
import ReactFlow, {
  Background,
  ConnectionMode,
  Controls,
  Edge,
  EdgeChange,
  type Connection,
  Node,
  NodeChange,
  type ReactFlowInstance,
  SelectionMode,
  type NodeTypes,
} from "reactflow";
import type { StrategyStep } from "@/features/strategy/types";
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
  selectedCount: number;
  onStartCombine?: () => void;
  onStartOrthologTransform?: () => void;
  canSave: boolean;
  onSave: () => void;
  onSaveDisabled?: () => void;
  saveDisabledReason?: string;
  isSaving: boolean;
  isUnsaved: boolean;
  nodes: Node[];
  edges: Edge[];
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onNodesDelete: (nodes: Node[]) => void;
  onNodeDragStop: () => void;
  onConnect: (connection: Connection) => void;
  isValidConnection: (connection: Connection) => boolean;
  nodeTypes: NodeTypes;
  onInit: (instance: ReactFlowInstance) => void;
  onMoveStart: () => void;
  onPaneClick?: (event: React.MouseEvent) => void;
  onEdgeClick?: (event: React.MouseEvent, edge: Edge) => void;
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
    selectedCount,
    onStartCombine,
    onStartOrthologTransform,
    canSave,
    onSave,
    onSaveDisabled,
    saveDisabledReason,
    isSaving,
    isUnsaved,
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onNodesDelete,
    onNodeDragStop,
    onConnect,
    isValidConnection,
    nodeTypes,
    onInit,
    onMoveStart,
    onPaneClick,
    onEdgeClick,
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
          selectedCount={selectedCount}
          onStartCombine={onStartCombine}
          onStartOrthologTransform={onStartOrthologTransform}
        />
        {!isCompact && (
          <StrategyGraphActionButtons
            canSave={canSave}
            onSave={onSave}
            onSaveDisabled={onSaveDisabled}
            saveDisabledReason={saveDisabledReason}
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
          isValidConnection={isValidConnection}
          nodeTypes={nodeTypes}
          defaultEdgeOptions={{ type: "step" }}
          onInit={onInit}
          onMoveStart={onMoveStart}
          onPaneClick={onPaneClick}
          onEdgeClick={onEdgeClick}
          selectionOnDrag={selectionOnDrag}
          selectionMode={SelectionMode.Partial}
          onSelectionChange={({ nodes: selectedNodes }) =>
            onSelectionChange(selectedNodes)
          }
          panOnDrag={panOnDrag}
          connectionMode={ConnectionMode.Loose}
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
          className="bg-muted"
        >
          <Background color="#e2e8f0" gap={28} size={1} />
          {!isCompact && (
            <Controls className="bg-card border-border text-muted-foreground" />
          )}
        </ReactFlow>
      </div>
    </div>
  );
}
