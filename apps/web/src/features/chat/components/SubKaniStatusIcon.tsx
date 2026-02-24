"use client";

import { CheckCircle2, CircleDashed, LoaderCircle, XCircle } from "lucide-react";

export function SubKaniStatusIcon(props: { status?: string; className?: string }) {
  const raw = (props.status || "").trim();
  const status = raw.toLowerCase();

  if (!status) {
    return (
      <span title="Status unknown">
        <CircleDashed
          className={props.className ?? "h-4 w-4 text-muted-foreground"}
          aria-label="Status unknown"
        />
      </span>
    );
  }

  if (status.includes("run")) {
    return (
      <span title="Running">
        <LoaderCircle
          className={props.className ?? "h-4 w-4 animate-spin text-muted-foreground"}
          aria-label="Running"
        />
      </span>
    );
  }

  if (
    status.includes("done") ||
    status.includes("success") ||
    status.includes("complete")
  ) {
    return (
      <span title={raw}>
        <CheckCircle2
          className={props.className ?? "h-4 w-4 text-success"}
          aria-label={raw}
        />
      </span>
    );
  }

  if (status.includes("error") || status.includes("fail")) {
    return (
      <span title={raw}>
        <XCircle
          className={props.className ?? "h-4 w-4 text-destructive"}
          aria-label={raw}
        />
      </span>
    );
  }

  return (
    <span title={raw}>
      <CircleDashed
        className={props.className ?? "h-4 w-4 text-muted-foreground"}
        aria-label={raw}
      />
    </span>
  );
}
