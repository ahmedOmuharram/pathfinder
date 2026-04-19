"use client";

import { cn } from "@/lib/utils/cn";
import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import type { ReactNode } from "react";
import { toast as sonnerToast } from "sonner";

export type ToastType = "success" | "error" | "info";

type ToastProps = {
  id: string | number;
  type: ToastType;
  description: string;
};

const iconsByType: Record<ToastType, ReactNode> = {
  success: <CheckCircle2 className="size-4" />,
  error: <AlertTriangle className="size-4" />,
  info: <Info className="size-4" />,
};

const iconClassByType: Record<ToastType, string> = {
  success: "text-green-600 dark:text-green-500",
  error: "text-red-600 dark:text-red-500",
  info: "text-foreground",
};

export function toast(props: Omit<ToastProps, "id">) {
  return sonnerToast.custom((id) => (
    <Toast description={props.description} id={id} type={props.type} />
  ));
}

function Toast({ id, type, description }: ToastProps) {
  return (
    <div className="flex w-full justify-center md:w-[356px]">
      <div
        className="flex w-full flex-row items-start gap-3 rounded-lg border border-border/50 bg-card p-3 shadow-[var(--shadow-float)] md:w-fit"
        data-testid="toast"
        key={id}
      >
        <div className={cn(iconClassByType[type], "pt-0.5")}>
          {iconsByType[type]}
        </div>
        <div className="text-sm text-foreground [overflow-wrap:anywhere]">
          {description}
        </div>
      </div>
    </div>
  );
}
