"use client";

import { cn } from "@/lib/utils/cn";
import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { useState, type ReactNode } from "react";
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
  const [isMultiLine, setIsMultiLine] = useState(false);

  const measureLines = (el: HTMLDivElement) => {
    const lineHeight = parseFloat(window.getComputedStyle(el).lineHeight);
    if (Number.isNaN(lineHeight) || lineHeight <= 0) return;
    setIsMultiLine(el.scrollHeight > lineHeight * 1.5);
  };

  const descriptionRef = (el: HTMLDivElement | null) => {
    if (el === null) return;
    measureLines(el);
    if (typeof window === "undefined" || !("ResizeObserver" in window)) return;
    const observer = new ResizeObserver(() => measureLines(el));
    observer.observe(el);
    return () => observer.disconnect();
  };

  return (
    <div className="flex w-full justify-center md:w-[356px]">
      <div
        className={cn(
          "flex w-full flex-row gap-3 rounded-lg border border-border/50 bg-card p-3 shadow-[var(--shadow-float)] md:w-fit",
          isMultiLine ? "items-start" : "items-center",
        )}
        data-testid="toast"
        key={id}
      >
        <div className={cn(iconClassByType[type], isMultiLine && "pt-0.5")}>
          {iconsByType[type]}
        </div>
        <div
          className="text-sm text-foreground [overflow-wrap:anywhere]"
          ref={descriptionRef}
        >
          {description}
        </div>
      </div>
    </div>
  );
}
