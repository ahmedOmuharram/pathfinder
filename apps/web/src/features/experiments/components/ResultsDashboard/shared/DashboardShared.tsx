import { Component, type ReactNode } from "react";
import { AlertCircle } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";

export class TabErrorBoundary extends Component<
  { children: ReactNode; onReset?: () => void },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-8 text-center">
          <AlertCircle className="h-5 w-5 text-destructive" />
          <p className="text-sm font-medium text-destructive">
            Something went wrong loading this tab.
          </p>
          <p className="max-w-md text-xs text-muted-foreground">
            {this.state.error.message}
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              this.setState({ error: null });
              this.props.onReset?.();
            }}
          >
            Try again
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}

export function NoStrategyNotice({ label }: { label?: string } = {}) {
  return (
    <div className="rounded-lg border border-border bg-muted/30 px-5 py-8 text-center text-sm text-muted-foreground">
      <AlertCircle className="mx-auto mb-2 h-5 w-5" />
      {label ??
        "This feature requires a persisted WDK strategy. Re-run the experiment to enable result browsing."}
    </div>
  );
}
