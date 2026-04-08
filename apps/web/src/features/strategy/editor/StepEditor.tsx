"use client";

import type { Step } from "@pathfinder/shared";
import { Modal } from "@/lib/components/Modal";
import { QueryBoundary } from "@/lib/components/QueryBoundary";
import { StepEditorHeader } from "./components/StepEditorHeader";
import { StepEditorFooter } from "./components/StepEditorFooter";
import { StepEditorForm } from "./StepEditorForm";
import { useStepEditorState } from "./useStepEditorState";

interface StepEditorProps {
  step: Step;
  siteId: string;
  recordType: string | null;
  onUpdate: (updates: Partial<Step>) => void;
  onClose: () => void;
}

export function StepEditor({
  step,
  siteId,
  recordType,
  onUpdate,
  onClose,
}: StepEditorProps) {
  return (
    <Modal open onClose={onClose} title="Edit step" maxWidth="max-w-4xl">
      <StepEditorHeader onClose={onClose} />
      <QueryBoundary>
        <StepEditorContent
          step={step}
          siteId={siteId}
          recordType={recordType}
          onUpdate={onUpdate}
          onClose={onClose}
        />
      </QueryBoundary>
      <StepEditorFooter onClose={onClose} />
    </Modal>
  );
}

function StepEditorContent(props: StepEditorProps) {
  const state = useStepEditorState(props);
  return <StepEditorForm state={state} />;
}
