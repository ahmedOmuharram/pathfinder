import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import type { ToastItem } from "@/app/hooks/useToasts";

interface ToastContainerProps {
  toasts: ToastItem[];
  durationMs: number;
  onDismiss: (id: string) => void;
}

export function ToastContainer({ toasts, durationMs, onDismiss }: ToastContainerProps) {
  if (toasts.length === 0) return null;

  return (
    <div className="pointer-events-none fixed right-6 top-6 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          style={
            {
              "--toast-duration": `${durationMs}ms`,
            } as React.CSSProperties
          }
          className={`toast-animate pointer-events-auto relative flex items-start gap-3 overflow-hidden rounded-lg border px-4 py-3 text-sm shadow-lg ${
            toast.type === "success"
              ? "border-success/20 bg-success/10 text-success"
              : toast.type === "warning"
                ? "border-amber-200 bg-amber-50 text-amber-900"
                : toast.type === "info"
                  ? "border-border bg-muted text-foreground"
                  : "border-destructive/30 bg-destructive/5 text-destructive"
          }`}
        >
          {toast.type === "success" && (
            <CheckCircle2 className="mt-0.5 h-4 w-4 text-success" />
          )}
          {toast.type === "warning" && (
            <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-600" />
          )}
          {toast.type === "info" && (
            <Info className="mt-0.5 h-4 w-4 text-muted-foreground" />
          )}
          {toast.type === "error" && (
            <XCircle className="mt-0.5 h-4 w-4 text-destructive" />
          )}
          <div className="flex-1">{toast.message}</div>
          <button
            type="button"
            onClick={() => onDismiss(toast.id)}
            className="mt-0.5 text-muted-foreground transition-colors duration-150 hover:text-foreground"
            aria-label="Dismiss notification"
          >
            ×
          </button>
          <div
            className={`toast-progress absolute bottom-0 left-0 h-1 ${
              toast.type === "success"
                ? "bg-success"
                : toast.type === "warning"
                  ? "bg-amber-400"
                  : toast.type === "info"
                    ? "bg-muted-foreground"
                    : "bg-destructive"
            }`}
          />
        </div>
      ))}
    </div>
  );
}
