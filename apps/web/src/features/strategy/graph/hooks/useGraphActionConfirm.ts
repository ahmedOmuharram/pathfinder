"use client";

import { useState } from "react";
import type { OperationChoice } from "@/features/strategy/operations";

interface ConfirmRequest<R extends string> {
  title: string;
  subtitle?: string | undefined;
  choices: OperationChoice<R>[];
  onResolve: (resolution: R) => void;
  confirmLabel?: string | undefined;
}

interface DialogProps<R extends string> {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  subtitle?: string | undefined;
  choices: OperationChoice<R>[];
  onConfirm: (resolution: R) => void;
  confirmLabel?: string | undefined;
}

export function useGraphActionConfirm<R extends string = string>(): {
  /** Open the dialog with a request. The `onResolve` callback fires once on Apply. */
  confirmAction: (req: ConfirmRequest<R>) => void;
  /** Close without resolving. */
  close: () => void;
  isOpen: boolean;
  /** Spread onto `<GraphActionConfirm>` when there is a pending request. */
  dialogProps: DialogProps<R> | null;
} {
  const [request, setRequest] = useState<ConfirmRequest<R> | null>(null);

  const close = (): void => setRequest(null);

  const confirmAction = (req: ConfirmRequest<R>): void => setRequest(req);

  const dialogProps: DialogProps<R> | null = request
    ? {
        open: true,
        onOpenChange: (next) => {
          if (!next) close();
        },
        title: request.title,
        subtitle: request.subtitle,
        choices: request.choices,
        onConfirm: (resolution) => {
          request.onResolve(resolution);
          close();
        },
        confirmLabel: request.confirmLabel,
      }
    : null;

  return {
    confirmAction,
    close,
    isOpen: request !== null,
    dialogProps,
  };
}
