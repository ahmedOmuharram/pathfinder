"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";

interface ModalProps {
  /** Controls visibility. The modal renders only when `true`. */
  open: boolean;
  /** Called when the user presses Escape, clicks outside, or presses the close button. */
  onClose: () => void;
  /** Optional title rendered as a visually-hidden accessible label. */
  title?: string;
  /** Max-width utility class (default: "max-w-md"). */
  maxWidth?: string;
  /** Whether to show a close (X) button in the top-right corner. */
  showCloseButton?: boolean;
  children: React.ReactNode;
}

/**
 * Shared modal shell built on @radix-ui/react-dialog.
 *
 * Provides:
 *  - Focus trapping
 *  - Escape key to close
 *  - Click-outside to close
 *  - Consistent overlay/backdrop
 *  - Accessible labelling
 */
export function Modal({
  open,
  onClose,
  title,
  maxWidth = "max-w-md",
  showCloseButton = false,
  children,
}: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={(next) => !next && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm data-[state=open]:animate-fade-in" />
        <Dialog.Content
          className={`fixed left-1/2 top-1/2 z-50 w-full -translate-x-1/2 -translate-y-1/2 rounded-lg border border-slate-200 bg-white p-0 shadow-xl focus:outline-none data-[state=open]:animate-fade-in ${maxWidth}`}
          aria-describedby={undefined}
        >
          {title && <Dialog.Title className="sr-only">{title}</Dialog.Title>}
          {showCloseButton && (
            <Dialog.Close asChild>
              <button
                type="button"
                className="absolute right-3 top-3 rounded-md p-1 text-slate-400 transition-colors hover:text-slate-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
                aria-label="Close"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </Dialog.Close>
          )}
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
