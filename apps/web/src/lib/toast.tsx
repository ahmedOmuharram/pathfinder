"use client";

import { cn } from "@/lib/utils/cn";
import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
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
  const descriptionRef = useRef<HTMLDivElement>(null);
  const [multiLine, setMultiLine] = useState(false);

  useEffect(() => {
    const el = descriptionRef.current;
    if (el === null) return undefined;

    const update = () => {
      const lineHeight = Number.parseFloat(getComputedStyle(el).lineHeight);
      const lines = Math.round(el.scrollHeight / lineHeight);
      setMultiLine(lines > 1);
    };

    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="flex w-full justify-center md:w-[356px]">
      <div
        className={cn(
          "flex w-full flex-row gap-3 rounded-lg border border-border/50 bg-card p-3 shadow-[var(--shadow-float)] md:w-fit",
          multiLine ? "items-start" : "items-center",
        )}
        data-testid="toast"
        key={id}
      >
        <div className={cn(iconClassByType[type], multiLine && "pt-0.5")}>
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
