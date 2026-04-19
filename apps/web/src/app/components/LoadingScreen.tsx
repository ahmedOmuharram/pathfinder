import { Loader2 } from "lucide-react";

export function LoadingScreen() {
  return (
    <div className="flex h-full flex-col items-center justify-center bg-background text-foreground">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      <p className="mt-3 text-sm text-muted-foreground">Loading...</p>
    </div>
  );
}
