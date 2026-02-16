import { Modal } from "@/shared/components/Modal";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";

interface DeleteConversationModalProps {
  target: ConversationItem | null;
  isDeleting: boolean;
  onClose: () => void;
  onConfirmDelete: () => void;
}

export function DeleteConversationModal({
  target,
  isDeleting,
  onClose,
  onConfirmDelete,
}: DeleteConversationModalProps) {
  return (
    <Modal
      open={!!target}
      onClose={onClose}
      title="Delete conversation"
      maxWidth="max-w-sm"
    >
      <div className="px-6 pb-6 pt-4">
        <p className="text-[13px] text-slate-600">
          Are you sure you want to delete{" "}
          <span className="font-semibold text-slate-900">
            &ldquo;{target?.title}&rdquo;
          </span>
          ? This cannot be undone.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={isDeleting}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-[12px] font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirmDelete}
            disabled={isDeleting}
            className="rounded-md bg-red-600 px-3 py-1.5 text-[12px] font-medium text-white transition hover:bg-red-700 disabled:opacity-60"
          >
            {isDeleting ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
