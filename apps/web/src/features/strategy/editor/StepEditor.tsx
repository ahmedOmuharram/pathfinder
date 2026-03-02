"use client";

import type { StrategyStep } from "@pathfinder/shared";
import { Modal } from "@/lib/components/Modal";
import { StepEditorHeader } from "./components/StepEditorHeader";
import { StepEditorFooter } from "./components/StepEditorFooter";
import { StepEditorForm } from "./StepEditorForm";
import { useStepEditorState } from "./useStepEditorState";

interface StepEditorProps {
  step: StrategyStep;
  siteId: string;
  recordType: string | null;
  onUpdate: (updates: Partial<StrategyStep>) => void;
  onClose: () => void;
}

export function StepEditor({
  step,
  siteId,
  recordType,
  onUpdate,
  onClose,
}: StepEditorProps) {
  const state = useStepEditorState({ step, siteId, recordType, onUpdate, onClose });

  return (
    <Modal open onClose={onClose} title="Edit step" maxWidth="max-w-4xl">
      <StepEditorHeader onClose={onClose} />
      <StepEditorForm state={state} />
      <StepEditorFooter onClose={onClose} onSave={state.handleSave} />
    </Modal>
  );
}
