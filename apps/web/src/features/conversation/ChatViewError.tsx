"use client";

import { AlertTriangle } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

/** The panel a thread that cannot render shows in place of the thread. */
export function ChatViewError({
  error,
  conversationsHref,
}: {
  error: unknown;
  conversationsHref: string;
}) {
  const detail = error instanceof Error ? error.message : String(error);
  return (
    <div
      role="alert"
      className="flex h-full min-w-0 flex-1 flex-col items-center justify-center gap-3 bg-card p-8 text-center"
    >
      <AlertTriangle className="h-6 w-6 text-destructive" />
      <h2 className="text-base font-semibold">This conversation cannot be shown.</h2>
      <p className="max-w-xl text-sm break-words text-muted-foreground">{detail}</p>
      <Button asChild variant="outline" size="sm">
        <Link href={conversationsHref}>Back to conversations</Link>
      </Button>
    </div>
  );
}
