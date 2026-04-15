"use client";

import { AlertCircle, RefreshCcw, X } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export function ChatErrorBanner({
  error,
  onRetry,
  onDismiss,
}: {
  error: Error;
  onRetry?: () => void;
  onDismiss?: () => void;
}) {
  return (
    <div
      className="mx-auto w-full max-w-3xl px-4 py-2"
      data-testid="chat-error-banner"
    >
      <Alert variant="destructive">
        <AlertCircle />
        <AlertTitle>The assistant turn errored</AlertTitle>
        <AlertDescription>
          <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words text-xs text-destructive/90">
            {error.message || String(error)}
          </pre>
          <div className="mt-2 flex gap-2">
            {onRetry ? (
              <Button
                size="sm"
                variant="outline"
                onClick={onRetry}
                className="gap-1"
              >
                <RefreshCcw className="size-3" />
                Retry
              </Button>
            ) : null}
            {onDismiss ? (
              <Button
                size="sm"
                variant="ghost"
                onClick={onDismiss}
                className="gap-1 text-muted-foreground"
              >
                <X className="size-3" />
                Dismiss
              </Button>
            ) : null}
          </div>
        </AlertDescription>
      </Alert>
    </div>
  );
}
