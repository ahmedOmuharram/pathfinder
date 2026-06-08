import { Loader2 } from "lucide-react";

export function StartupScreen({ notReady }: { notReady: string[] }) {
  return (
    <div className="flex h-full flex-col items-center justify-center bg-background text-foreground">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      <p className="mt-3 text-sm text-muted-foreground">Starting up...</p>
      {notReady.length > 0 && (
        <p className="mt-1 text-xs text-muted-foreground/70">
          Waiting for {notReady.join(", ")}
        </p>
      )}
    </div>
  );
}
