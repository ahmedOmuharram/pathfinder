"use client";

import { useState } from "react";
import { AlertTriangle, Archive, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useSessionStore } from "@/state/useSessionStore";
import { usePlanStore } from "@/state/usePlanStore";
import { useConversationSidebarData } from "@/features/sidebar/hooks/useConversationSidebarData";
import { useConversationSidebarActions } from "@/features/sidebar/hooks/useConversationSidebarActions";
import { ConversationList } from "@/features/sidebar/components/ConversationList";
import { DeleteConversationModal } from "@/features/sidebar/components/DeleteConversationModal";
import { DuplicateConversationModal } from "@/features/sidebar/components/DuplicateConversationModal";

interface ConversationSidebarProps {
  siteId: string;
}

export function ConversationSidebar({ siteId }: ConversationSidebarProps) {
  const chatIsStreaming = useSessionStore((s) => s.chatIsStreaming);
  const currentPhase = usePlanStore((s) => s.currentPhase);
  const phaseStatus = usePlanStore((s) => s.phaseStatus);

  const reportError = (message: string) => toast.error(message);

  const [showDismissed, setShowDismissed] = useState(false);

  const data = useConversationSidebarData({ siteId });
  const actions = useConversationSidebarActions({
    siteId,
    reportError,
  });

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 px-3 py-4">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Conversations
        </div>
        <div className="flex items-center gap-1">
          <Button
            data-testid="conversations-refresh-button"
            type="button"
            variant="ghost"
            size="icon-sm"
            disabled={chatIsStreaming || data.isSyncing}
            onClick={() => void data.handleManualRefresh()}
            title="Refresh conversations & strategies"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${data.isSyncing ? "animate-spin" : ""}`}
            />
          </Button>
          <Button
            data-testid="conversations-new-button"
            type="button"
            variant="outline"
            size="sm"
            disabled={chatIsStreaming}
            onClick={() => void actions.handleNewConversation()}
            aria-label="New chat"
          >
            New Chat
          </Button>
        </div>
      </div>

      <Input
        data-testid="conversations-search-input"
        value={data.query}
        onChange={(e) => data.setQuery(e.target.value)}
        placeholder="Search conversations..."
        aria-label="Search conversations"
        className="bg-card"
      />

      {(!data.hasInitiallyLoaded || data.isSyncing) && data.filtered.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-2 py-10 text-muted-foreground animate-fade-in">
          <Spinner className="h-5 w-5" />
          <p className="text-xs">Loading conversations…</p>
        </div>
      )}

      <ConversationList
        items={data.filtered}
        query={data.query}
        hasInitiallyLoaded={data.hasInitiallyLoaded}
        activeId={actions.activeId}
        renamingId={actions.renamingId}
        renameValue={actions.renameValue}
        chatIsStreaming={chatIsStreaming}
        currentPhase={currentPhase}
        phaseStatus={phaseStatus}
        onRenameValueChange={actions.setRenameValue}
        onCommitRename={(target) => void actions.commitRename(target)}
        onCancelRename={actions.cancelRename}
        onSelect={actions.handleSelect}
        onStartRename={actions.startRename}
        onStartDelete={actions.setDeleteTarget}
        onStartDuplicate={actions.setDuplicateTarget}
        onToggleSaved={(item) => void actions.handleToggleSaved(item)}
      />

      {data.dismissedConversations.length > 0 && (
        <>
          <Button
            data-testid="dismissed-toggle"
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setShowDismissed((prev) => !prev)}
            className="h-7 justify-start gap-1.5 px-1 text-xs font-normal text-muted-foreground"
          >
            <Archive className="h-3 w-3" />
            <span>Dismissed ({data.dismissedConversations.length})</span>
            <span className="ml-auto text-[10px]">
              {showDismissed ? "\u25BC" : "\u25B6"}
            </span>
          </Button>
          {showDismissed && (
            <div className="space-y-0.5 pl-1">
              {data.dismissedConversations.map((item) => (
                <div
                  key={item.id}
                  data-testid="dismissed-item"
                  data-conversation-id={item.id}
                  className="flex items-center justify-between rounded-md px-2 py-1.5 text-xs text-muted-foreground"
                >
                  <span className="min-w-0 truncate">{item.title}</span>
                  <div className="ml-2 flex shrink-0 items-center gap-1">
                    <Button
                      data-testid="dismissed-restore-button"
                      type="button"
                      variant="ghost"
                      size="xs"
                      onClick={() => void actions.handleRestore(item.id)}
                    >
                      Restore
                    </Button>
                    <Button
                      data-testid="dismissed-delete-button"
                      type="button"
                      variant="ghost"
                      size="xs"
                      onClick={() => actions.setPermanentDeleteTarget(item.id)}
                      className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      <DeleteConversationModal
        target={actions.deleteTarget}
        isDeleting={actions.isDeleting}
        onClose={() => actions.setDeleteTarget(null)}
        onConfirmDelete={() => void actions.confirmDelete()}
      />

      <DuplicateConversationModal
        target={actions.duplicateTarget}
        isDuplicating={actions.isDuplicating}
        onClose={() => actions.setDuplicateTarget(null)}
        onConfirm={() => void actions.confirmDuplicate()}
      />

      <Dialog
        open={actions.permanentDeleteTarget !== null}
        onOpenChange={(open) => !open && actions.setPermanentDeleteTarget(null)}
      >
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Permanently delete conversation</DialogTitle>
            <DialogDescription className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
              <span>
                This permanently removes the conversation and all its messages.
                This cannot be undone.
              </span>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => actions.setPermanentDeleteTarget(null)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => void actions.confirmPermanentDelete()}
            >
              Delete permanently
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
