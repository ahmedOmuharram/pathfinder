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
} from "@/features/strategy/mutations";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/strategy/store";
import { useStrategyData } from "@/state/strategy/useStrategyQuery";
import { useStrategyDraft, type StrategyDraft } from "@/state/strategy/useStrategyDraft";
import { useStepSnapshot } from "@/state/strategy/useStepSnapshot";
import { EditorHeader } from "./EditorHeader";
import { EditorBody } from "./EditorBody";
import { EditorFooter, type SyncState } from "./EditorFooter";
import { useStepEditorState } from "./useStepEditorState";
import { useEditorAutoSave } from "./hooks/useEditorAutoSave";
import { DEFAULT_COLOCATION } from "./components/ColocationEditor";

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
  const draft = useStrategyDraft(conversationId);
  const handleOpenChange = (next: boolean) => {
    if (!next) draft.flush();
    onOpenChange(next);
  };
  return (
    <Sheet open={isOpen} onOpenChange={handleOpenChange}>
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
              draft={draft}
              onClose={() => handleOpenChange(false)}
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
  draft: StrategyDraft;
  onClose: () => void;
}

function EditorContent({
  step,
  siteId,
  recordType,
  conversationId,
  draft,
  onClose,
}: EditorContentProps) {
  const state = useStepEditorState({ step, siteId, recordType });
  const deleteStep = useDeleteStepMutation(conversationId);
  const duplicateStep = useDuplicateStepMutation(conversationId);
  const stepNumber = useStepNumber(conversationId, step.id);
  const wdkUrl = useStrategyData(conversationId)?.wdkUrl ?? null;
  const isPaused = useGraphValidationPaused(conversationId);
  const snapshot = useStepSnapshot(step);

  const autosave = useEditorAutoSave({
    debounceMs: 500,
    mutation: {
      mutate: (vars) => {
        draft.applyStepPatch(vars.stepId, vars.patch);
      },
      isPending: false,
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
    draft.applyStepPatch(step.id, { displayName: next });
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
    draft.applyStepPatch(step.id, patch);
  };

  const handleOperatorChange = (operator: string): void => {
    if (operator === step.operator) return;
    state.setOperatorValue(operator);
    const patch: Partial<Step> = { operator };
    if (operator === "COLOCATE") {
      patch.colocationParams = step.colocationParams ?? DEFAULT_COLOCATION;
    } else {
      patch.colocationParams = null;
    }
    draft.applyStepPatch(step.id, patch);
  };

  const handleColocationChange = (
    next: NonNullable<Step["colocationParams"]>,
  ): void => {
    state.setColocationParams(next);
    draft.applyStepPatch(step.id, { colocationParams: next });
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
    updatePending: draft.isFlushing,
    updateError: false,
  });

  const dbName = useSessionStore((s) => s.selectedSiteDisplayName);
  const footerProps = {
    syncState,
    count: snapshot.estimatedSize,
    wdkUrl,
    dbName,
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

function useGraphValidationPaused(conversationId: string): boolean {
  const status = useStrategyStore((s) => s.graphValidationStatus);
  return status[conversationId] === true;
}

function useStepNumber(conversationId: string, stepId: string): number | null {
  const steps = useStrategyData(conversationId)?.steps ?? [];
  const idx = steps.findIndex((s) => s.id === stepId);
  return idx >= 0 ? idx + 1 : null;
}
