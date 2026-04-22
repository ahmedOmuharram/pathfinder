"use client";

import { toast } from "sonner";
import type { Step } from "@pathfinder/shared";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { QueryBoundary } from "@/lib/components/QueryBoundary";
import {
  useDeleteStepMutation,
  useDuplicateStepMutation,
  useUpdateStepMutation,
} from "@/features/strategy/mutations";
import { useStrategyStore } from "@/state/strategy/store";
import { useStepSnapshot } from "@/state/strategy/useStepSnapshot";
import { EditorHeader } from "./EditorHeader";
import { EditorBody } from "./EditorBody";
import { EditorFooter, type SyncState } from "./EditorFooter";
import { useStepEditorState } from "./useStepEditorState";
import { useEditorAutoSave } from "./hooks/useEditorAutoSave";

interface EditorProps {
  step: Step | null;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  siteId: string;
  recordType: string | null;
  conversationId: string;
}



export function Editor({
  step,
  isOpen,
  onOpenChange,
  siteId,
  recordType,
  conversationId,
}: EditorProps) {
  return (
    <Sheet open={isOpen} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        data-testid="step-editor-sheet"
        className="flex w-[440px] flex-col gap-0 p-0 sm:max-w-[440px]"
      >
        <SheetHeader className="sr-only">
          <SheetTitle>Edit step</SheetTitle>
          <SheetDescription>
            Edit parameters for the selected strategy step.
          </SheetDescription>
        </SheetHeader>
        {step !== null && (
          <QueryBoundary>
            <EditorContent
              key={step.id}
              step={step}
              siteId={siteId}
              recordType={recordType}
              conversationId={conversationId}
              onClose={() => onOpenChange(false)}
            />
          </QueryBoundary>
        )}
      </SheetContent>
    </Sheet>
  );
}

interface EditorContentProps {
  step: Step;
  siteId: string;
  recordType: string | null;
  conversationId: string;
  onClose: () => void;
}

function EditorContent({
  step,
  siteId,
  recordType,
  conversationId,
  onClose,
}: EditorContentProps) {
  const state = useStepEditorState({ step, siteId, recordType });
  const updateStep = useUpdateStepMutation();
  const deleteStep = useDeleteStepMutation();
  const duplicateStep = useDuplicateStepMutation();
  const stepNumber = useStepNumber(step.id);
  const wdkUrl = useStrategyStore((s) => s.strategy?.wdkUrl ?? null);
  const isPaused = useGraphValidationPaused();
  const snapshot = useStepSnapshot(step.id);

  const autosave = useEditorAutoSave({
    debounceMs: 500,
    mutation: {
      mutate: (vars) => {
        updateStep.mutate(vars);
      },
      isPending: updateStep.isPending,
    },
    getPayload: () => {
      const values = state.form.state.values;
      const allowedKeys = new Set(
        state.paramSpecs
          .filter((s) => s.name !== "" && s.isVisible !== false)
          .map((s) => s.name),
      );
      const parameters: Record<string, string | string[]> = {};
      for (const [key, val] of Object.entries(values)) {
        if (allowedKeys.has(key)) {
          parameters[key] = val;
        }
      }
      for (const [key, val] of Object.entries(state.hiddenDefaults)) {
        if (typeof val === "string" || Array.isArray(val)) {
          parameters[key] = val as string | string[];
        } else if (val != null) {
          parameters[key] = String(val);
        }
      }
      return {
        stepId: step.id,
        patch: { parameters },
      };
    },
  });

  const handleRename = (next: string): void => {
    updateStep.mutate({ stepId: step.id, patch: { displayName: next } });
  };

  const handleDelete = (): void => {
    deleteStep.mutate({ stepId: step.id });
    onClose();
  };

  const handleDuplicate = (): void => {
    duplicateStep.mutate({ stepId: step.id });
  };

  const handleCopyUrl = (): void => {
    if (typeof window === "undefined") return;
    const origin = window.location.origin;
    const url = `${origin}/${siteId}/conversation/${conversationId}/strategy/step/${step.id}`;
    void navigator.clipboard.writeText(url);
    toast.success("Step URL copied");
  };

  const handleSearchChange = (next: string | null): void => {
    if (next === null || next === step.searchName) return;
    state.setEditableSearchName(next);
    const picked = state.searchOptions.find((s) => s.name === next);
    const nextRecordType = picked?.recordType ?? step.recordType ?? null;
    const patch: Partial<Step> = { searchName: next };
    if (nextRecordType !== null) {
      patch.recordType = nextRecordType;
    }
    updateStep.mutate({ stepId: step.id, patch });
  };

  const handleOperatorChange = (operator: string): void => {
    if (operator === step.operator) return;
    state.setOperatorValue(operator);
    updateStep.mutate({ stepId: step.id, patch: { operator } });
  };

  const handleColocationChange = (
    next: NonNullable<Step["colocationParams"]>,
  ): void => {
    state.setColocationParams(next);
    updateStep.mutate({ stepId: step.id, patch: { colocationParams: next } });
  };

  const handleFieldChanged = (
    name: string,
    value: unknown,
    allValues: Record<string, unknown>,
  ): void => {
    state.onDependentFieldChange(name, value, allValues);
    autosave.scheduleSave();
  };

  const handleFieldBlurred = (): void => {
    autosave.submitNow();
  };

  const syncState = computeSyncState({
    isPaused,
    updatePending: updateStep.isPending,
    updateError: updateStep.isError,
  });

  const footerProps = {
    syncState,
    count: snapshot.estimatedSize,
    wdkUrl,
    ...(updateStep.isError && {
      onRetry: () => {
        autosave.submitNow();
      },
    }),
  };

  return (
    <div className="flex h-full flex-col">
      <EditorHeader
        step={step}
        kind={state.kind}
        stepNumber={stepNumber}
        onRename={handleRename}
        onDelete={handleDelete}
        onDuplicate={handleDuplicate}
        onCopyUrl={handleCopyUrl}
      />
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <EditorBody
          state={state}
          step={step}
          onSearchChange={handleSearchChange}
          onOperatorChange={handleOperatorChange}
          onColocationChange={handleColocationChange}
          onFieldChanged={handleFieldChanged}
          onFieldBlurred={handleFieldBlurred}
        />
      </div>
      <EditorFooter {...footerProps} />
    </div>
  );
}

function computeSyncState(args: {
  isPaused: boolean;
  updatePending: boolean;
  updateError: boolean;
}): SyncState {
  if (args.isPaused) return "paused";
  if (args.updatePending) return "saving";
  if (args.updateError) return "error";
  return "idle";
}

function useGraphValidationPaused(): boolean {
  const strategyId = useStrategyStore((s) => s.strategy?.id ?? null);
  const status = useStrategyStore((s) => s.graphValidationStatus);
  if (strategyId === null) return false;
  return status[strategyId] === true;
}

function useStepNumber(stepId: string): number | null {
  const steps = useStrategyStore((s) => s.strategy?.steps ?? []);
  const idx = steps.findIndex((s) => s.id === stepId);
  return idx >= 0 ? idx + 1 : null;
}
