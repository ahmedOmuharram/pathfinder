"use client";

import { Layers, MessageCircle, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/lib/components/ui/Button";

interface EmbeddedToolbarProps {
  onOpenSettings: () => void;
}

export function EmbeddedToolbar({ onOpenSettings }: EmbeddedToolbarProps) {
  const pathname = usePathname();
  const chatActive = pathname === "/chat" || pathname.startsWith("/chat/");
  const workbenchActive =
    pathname === "/workbench" || pathname.startsWith("/workbench/");

  return (
    <div className="flex items-center justify-end gap-1 border-b border-border bg-background px-3 py-1">
      <Link
        href="/chat"
        aria-label="Go to Chat"
        aria-current={chatActive ? "page" : undefined}
        className={
          chatActive
            ? "inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground"
            : "inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium text-muted-foreground transition-all duration-150 hover:bg-accent hover:text-accent-foreground"
        }
      >
        <MessageCircle className="h-3.5 w-3.5" aria-hidden />
        Chat
      </Link>
      <Link
        href="/workbench"
        aria-label="Go to Workbench"
        aria-current={workbenchActive ? "page" : undefined}
        className={
          workbenchActive
            ? "inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground"
            : "inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium text-muted-foreground transition-all duration-150 hover:bg-accent hover:text-accent-foreground"
        }
      >
        <Layers className="h-3.5 w-3.5" aria-hidden />
        Workbench
      </Link>
      <div className="mx-1 h-4 w-px bg-border" />
      <Button
        variant="ghost"
        size="icon"
        onClick={onOpenSettings}
        aria-label="Settings"
        className="h-7 w-7"
      >
        <Settings className="h-3.5 w-3.5" aria-hidden />
      </Button>
    </div>
  );
}
