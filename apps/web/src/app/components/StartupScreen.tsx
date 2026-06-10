import { AlertTriangle, Loader2 } from "lucide-react";
import type { SystemReadyResponse } from "@pathfinder/shared/generated/types/SystemReadyResponse";

export type StartupStatus =
  | { kind: "booting"; notReady: string[] }
  | { kind: "degraded"; notReady: string[] }
  | { kind: "unreachable" };

export function startupStatus(args: {
  data: SystemReadyResponse | undefined;
  isError: boolean;
  elapsedMs: number;
  graceMs: number;
}): StartupStatus {
  const notReady = args.data?.notReady ?? [];
  if (args.elapsedMs < args.graceMs) {
    return { kind: "booting", notReady };
  }
  if (args.isError || args.data === undefined) {
    return { kind: "unreachable" };
  }
  return { kind: "degraded", notReady };
}

export function StartupScreen({ status }: { status: StartupStatus }) {
  if (status.kind === "booting") {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-background text-foreground">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="mt-3 text-sm text-muted-foreground">Starting up...</p>
        {status.notReady.length > 0 && (
          <p className="mt-1 text-xs text-muted-foreground/70">
            Waiting for {status.notReady.join(", ")}
          </p>
        )}
      </div>
    );
  }

  const title =
    status.kind === "unreachable"
      ? "Can't reach the server"
      : "Some services failed to start";
  const detail =
    status.kind === "unreachable"
      ? "The API isn't responding."
      : `These subsystems aren't ready: ${status.notReady.join(", ")}.`;

  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 bg-background px-6 text-center text-foreground">
      <AlertTriangle className="h-8 w-8 text-destructive" />
      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="mx-auto mt-1 max-w-sm text-xs text-muted-foreground">{detail}</p>
        <p className="mx-auto mt-2 max-w-sm text-xs text-muted-foreground/70">
          Please report this to an administrator.
        </p>
      </div>
    </div>
  );
}
