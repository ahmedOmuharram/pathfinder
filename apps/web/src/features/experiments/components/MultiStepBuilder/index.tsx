"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  type Edge,
  type Node,
  useNodesState,
  useEdgesState,
  type ReactFlowInstance,
  type NodeTypes,
} from "reactflow";
import "reactflow/dist/style.css";
import ReactFlow, { Background, Controls, MiniMap, Panel } from "reactflow";
import { ArrowLeft, GitBranch, Import, Plus, RefreshCw, Search } from "lucide-react";
import { CombineOperator } from "@pathfinder/shared";
import type { StrategyStep } from "@/features/strategy/types";
import { StepNode } from "@/features/strategy/graph/components/StepNode";
import { CombineStepModal } from "@/features/strategy/graph/components/CombineStepModal";
import type { PendingCombine } from "@/features/strategy/graph/components/CombineStepModal";
import { deserializeStrategyToGraph } from "@/lib/strategyGraph";
import { Button } from "@/lib/components/ui/Button";
import { useMultiStepBuilder } from "./useMultiStepBuilder";
import { ConfigPanel } from "./ConfigPanel";
import { StrategyImportModal } from "./StrategyImportModal";
import { ExperimentStepModal } from "./ExperimentStepModal";
import { ControlsModal } from "./ControlsModal";

const NODE_TYPES: NodeTypes = { step: StepNode };
const SNAP_GRID: [number, number] = [28, 28];
const COMBINE_OPERATORS = Object.values(CombineOperator);

interface MultiStepBuilderProps {
  siteId: string;
}

export function MultiStepBuilder({ siteId }: MultiStepBuilderProps) {
  const builder = useMultiStepBuilder(siteId);
  const {
    strategy,
    steps,
    selectedRecordType,
    recordTypes,
    searches,
    searchFilter,
    setSearchFilter,
    selectedStep,
    selectedStepId,
    setSelectedStepId,
    importModalOpen,
    setImportModalOpen,
    addSearchStep,
    addCombineStep,
    updateStep,
    removeStep,
    loadImportedSteps,
    handleRecordTypeChange,
    goBack,
  } = builder;

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [pendingCombine, setPendingCombine] = useState<PendingCombine | null>(null);
  const [showSearchPicker, setShowSearchPicker] = useState(false);
  const [controlsModalOpen, setControlsModalOpen] = useState(false);
  const reactFlowRef = useRef<ReactFlowInstance | null>(null);

  const handleOpenDetails = useCallback(
    (stepId: string) => setSelectedStepId(stepId),
    [setSelectedStepId],
  );

  const nodeTypes = useMemo(() => NODE_TYPES, []);

  useEffect(() => {
    const { nodes: newNodes, edges: newEdges } = deserializeStrategyToGraph(
      strategy,
      (stepId, operator) => {
        updateStep(stepId, { operator: operator as StrategyStep["operator"] });
      },
      undefined,
      handleOpenDetails,
      undefined,
      { forceRelayout: true },
    );
    setNodes(newNodes);
    setEdges(newEdges);
  }, [strategy, setNodes, setEdges, updateStep, handleOpenDetails]);

  useEffect(() => {
    if (nodes.length > 0) {
      setTimeout(() => {
        reactFlowRef.current?.fitView({ padding: 0.3, duration: 300 });
      }, 50);
    }
  }, [nodes.length]);

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      setSelectedStepId(node.id);
    },
    [setSelectedStepId],
  );

  const handleNodesDelete = useCallback(
    (deletedNodes: Node[]) => {
      for (const node of deletedNodes) {
        removeStep(node.id);
      }
    },
    [removeStep],
  );

  const handleCombineSelection = useCallback(() => {
    if (steps.length < 2) return;
    const rootSteps = steps.filter(
      (s) =>
        !steps.some(
          (other) =>
            other.primaryInputStepId === s.id || other.secondaryInputStepId === s.id,
        ),
    );
    if (rootSteps.length >= 2) {
      setPendingCombine({
        sourceId: rootSteps[0]!.id,
        targetId: rootSteps[1]!.id,
      });
    }
  }, [steps]);

  const handleCombineCreate = useCallback(
    (operator: string) => {
      if (!pendingCombine) return;
      addCombineStep(
        pendingCombine.sourceId,
        pendingCombine.targetId,
        operator as CombineOperator,
      );
      setPendingCombine(null);
    },
    [pendingCombine, addCombineStep],
  );

  const handleImport = useCallback(
    (
      importedSteps: StrategyStep[],
      importedName: string,
      importedRecordType: string,
    ) => {
      loadImportedSteps(importedSteps, importedRecordType || undefined);
      builder.setName(importedName + " (experiment)");
      setImportModalOpen(false);
    },
    [loadImportedSteps, builder, setImportModalOpen],
  );

  return (
    <div className="flex h-full">
      {/* Left: Graph Panel */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Toolbar */}
        <div className="flex items-center gap-2 border-b border-border bg-card px-4 py-2">
          <Button variant="ghost" size="sm" onClick={goBack}>
            <ArrowLeft className="h-3.5 w-3.5" />
            Back
          </Button>
          <div className="mx-1 h-5 w-px bg-border" />

          {/* Record type selector */}
          <select
            value={selectedRecordType}
            onChange={(e) => handleRecordTypeChange(e.target.value)}
            className="rounded border border-input bg-background px-2 py-1 text-xs focus:border-primary focus:outline-none"
          >
            {recordTypes.map((rt) => (
              <option key={rt.name} value={rt.name}>
                {rt.displayName || rt.name}
              </option>
            ))}
          </select>

          <div className="mx-1 h-5 w-px bg-border" />

          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowSearchPicker(!showSearchPicker)}
          >
            <Plus className="h-3 w-3" />
            Add Search
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCombineSelection}
            disabled={steps.length < 2}
          >
            <GitBranch className="h-3 w-3" />
            Combine
          </Button>
          <Button variant="outline" size="sm" onClick={() => setImportModalOpen(true)}>
            <Import className="h-3 w-3" />
            Import
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={builder.refreshCounts}
            title="Refresh step result counts"
            disabled={!builder.planResult}
          >
            <RefreshCw className="h-3 w-3" />
          </Button>

          <div className="flex-1" />

          <span className="text-xs text-muted-foreground">
            {steps.length} step{steps.length !== 1 ? "s" : ""}
            {builder.treeOpt.enabled && (
              <span className="ml-1 text-primary">(tree opt on)</span>
            )}
          </span>
        </div>

        {/* Search Picker Dropdown */}
        {showSearchPicker && (
          <div className="border-b border-border bg-card/50 px-4 py-3">
            <div className="flex items-center gap-2">
              <Search className="h-3.5 w-3.5 text-muted-foreground" />
              <input
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="Filter searches..."
                className="flex-1 rounded border border-input bg-background px-2 py-1 text-xs placeholder:text-muted-foreground focus:border-primary focus:outline-none"
                autoFocus
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowSearchPicker(false)}
              >
                Done
              </Button>
            </div>
            <div className="mt-2 max-h-48 overflow-y-auto">
              {searches.length === 0 && (
                <p className="py-2 text-center text-xs text-muted-foreground">
                  {searchFilter ? "No searches match filter" : "Loading searches..."}
                </p>
              )}
              {searches.map((search) => (
                <button
                  key={search.name}
                  onClick={() => {
                    addSearchStep(search.name, search.displayName);
                    setShowSearchPicker(false);
                    setSearchFilter("");
                  }}
                  className="w-full rounded px-2 py-1.5 text-left text-xs text-foreground transition-colors hover:bg-accent"
                >
                  <span className="font-medium">{search.displayName}</span>
                  <span className="ml-2 text-muted-foreground">{search.name}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Graph Area */}
        <div className="min-h-0 flex-1">
          {steps.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-muted-foreground">
              <GitBranch className="h-12 w-12 opacity-30" />
              <div className="text-center">
                <p className="text-sm font-medium">Build your strategy graph</p>
                <p className="mt-1 text-xs">
                  Add search steps using the toolbar, combine them with boolean
                  operators, or import an existing strategy.
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowSearchPicker(true)}
                >
                  <Plus className="h-3 w-3" />
                  Add Search
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setImportModalOpen(true)}
                >
                  <Import className="h-3 w-3" />
                  Import Strategy
                </Button>
              </div>
            </div>
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={handleNodeClick}
              onNodesDelete={handleNodesDelete}
              nodeTypes={nodeTypes}
              onInit={(instance) => {
                reactFlowRef.current = instance;
              }}
              snapToGrid
              snapGrid={SNAP_GRID}
              fitView
              fitViewOptions={{ padding: 0.3 }}
              deleteKeyCode={["Backspace", "Delete"]}
              className="bg-background"
            >
              <Background gap={28} size={1} />
              <Controls showInteractive={false} />
              <MiniMap nodeStrokeWidth={3} zoomable pannable className="!bg-card" />
              {builder.warnings.length > 0 && (
                <Panel position="top-right">
                  <div className="space-y-1">
                    {builder.warnings.map((w, i) => (
                      <div
                        key={i}
                        className={`rounded-md px-2 py-1 text-xs ${
                          w.severity === "error"
                            ? "bg-destructive/10 text-destructive"
                            : "bg-yellow-500/10 text-yellow-700 dark:text-yellow-400"
                        }`}
                      >
                        {w.message}
                      </div>
                    ))}
                  </div>
                </Panel>
              )}
            </ReactFlow>
          )}
        </div>
      </div>

      {/* Right: Config Panel */}
      <div className="w-80 shrink-0">
        <ConfigPanel
          siteId={siteId}
          name={builder.name}
          onNameChange={builder.setName}
          positiveGenes={builder.positiveGenes}
          onPositiveGenesChange={builder.setPositiveGenes}
          negativeGenes={builder.negativeGenes}
          onNegativeGenesChange={builder.setNegativeGenes}
          onOpenControlsModal={() => setControlsModalOpen(true)}
          enableCV={builder.enableCV}
          onEnableCVChange={builder.setEnableCV}
          kFolds={builder.kFolds}
          kFoldsDraft={builder.kFoldsDraft}
          onKFoldsChange={builder.setKFolds}
          onKFoldsDraftChange={builder.setKFoldsDraft}
          enrichments={builder.enrichments}
          onToggleEnrichment={builder.toggleEnrichment}
          treeOpt={builder.treeOpt}
          onTreeOptChange={builder.setTreeOpt}
          warnings={builder.warnings}
          canRun={builder.canRun}
          isRunning={builder.isRunning}
          storeError={builder.storeError}
          onRun={builder.handleRun}
        />
      </div>

      {/* Modals */}
      <CombineStepModal
        pendingCombine={pendingCombine}
        operators={COMBINE_OPERATORS}
        onChoose={handleCombineCreate}
        onCancel={() => setPendingCombine(null)}
      />

      {selectedStep && (
        <ExperimentStepModal
          step={selectedStep}
          siteId={siteId}
          recordType={selectedRecordType}
          onUpdate={(updates) => updateStep(selectedStep.id, updates)}
          onClose={() => setSelectedStepId(null)}
        />
      )}

      <ControlsModal
        open={controlsModalOpen}
        siteId={siteId}
        positiveGenes={builder.positiveGenes}
        onPositiveGenesChange={builder.setPositiveGenes}
        negativeGenes={builder.negativeGenes}
        onNegativeGenesChange={builder.setNegativeGenes}
        onClose={() => setControlsModalOpen(false)}
      />

      <StrategyImportModal
        open={importModalOpen}
        siteId={siteId}
        onImport={handleImport}
        onClose={() => setImportModalOpen(false)}
      />
    </div>
  );
}
