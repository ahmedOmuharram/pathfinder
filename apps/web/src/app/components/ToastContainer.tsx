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
    <div className="fixed right-6 top-6 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          style={
            {
              "--toast-duration": `${durationMs}ms`,
            } as React.CSSProperties
          }
          className={`toast-animate relative flex items-start gap-3 overflow-hidden rounded-lg border px-4 py-3 text-sm shadow-lg ${
            toast.type === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-900"
              : toast.type === "warning"
                ? "border-amber-200 bg-amber-50 text-amber-900"
                : toast.type === "info"
                  ? "border-slate-200 bg-slate-50 text-slate-900"
                  : "border-red-200 bg-red-50 text-red-900"
          }`}
        >
          {toast.type === "success" && (
            <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" />
          )}
          {toast.type === "warning" && (
            <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-600" />
          )}
          {toast.type === "info" && <Info className="mt-0.5 h-4 w-4 text-slate-600" />}
          {toast.type === "error" && <XCircle className="mt-0.5 h-4 w-4 text-red-600" />}
          <div className="flex-1">{toast.message}</div>
          <button
            type="button"
            onClick={() => onDismiss(toast.id)}
            className="mt-0.5 text-slate-500 hover:text-slate-700"
            aria-label="Dismiss notification"
          >
            ×
          </button>
          <div
            className={`toast-progress absolute bottom-0 left-0 h-1 ${
              toast.type === "success"
                ? "bg-emerald-400"
                : toast.type === "warning"
                  ? "bg-amber-400"
                  : toast.type === "info"
                    ? "bg-slate-400"
                    : "bg-red-400"
            }`}
          />
        </div>
      ))}
    </div>
  );
}
