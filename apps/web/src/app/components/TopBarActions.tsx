"use client";

import { Brain, Layers, MessageCircle, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/lib/components/ui/Button";

interface TopBarActionsProps {
  onOpenSettings: () => void;
  onOpenEngine: () => void;
}

export function TopBarActions({ onOpenSettings, onOpenEngine }: TopBarActionsProps) {
  const pathname = usePathname();
  const chatActive = pathname === "/conversation" || pathname.startsWith("/conversation/") || pathname.startsWith("/conversation/");
  const workbenchActive =
    pathname === "/workbench" || pathname.startsWith("/workbench/");

  return (
    <div className="flex items-center gap-1">
      <Link
        href="/conversation"
        aria-label="Go to Chat"
        aria-current={chatActive ? "page" : undefined}
        className={
          chatActive
            ? "inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
            : "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium text-muted-foreground transition-all duration-150 hover:bg-accent hover:text-accent-foreground"
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
            ? "inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
            : "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium text-muted-foreground transition-all duration-150 hover:bg-accent hover:text-accent-foreground"
        }
      >
        <Layers className="h-3.5 w-3.5" aria-hidden />
        Workbench
      </Link>
      <div className="mx-1 h-5 w-px bg-border" />
      <Button
        variant="ghost"
        size="icon"
        onClick={onOpenEngine}
        aria-label="AI Engine"
      >
        <Brain className="h-4 w-4" aria-hidden />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        onClick={onOpenSettings}
        aria-label="Settings"
      >
        <Settings className="h-4 w-4" aria-hidden />
      </Button>
    </div>
  );
}
