"use client";

import { useCallback, useState } from "react";
import { Bookmark, Loader2 } from "lucide-react";
import { createControlSet } from "../api/controlSets";
import { Button } from "@/lib/components/ui/Button";
import { Input } from "@/lib/components/ui/Input";

interface SaveControlSetFormProps {
  siteId: string;
  positiveIds: string[];
  negativeIds: string[];
  recordType?: string;
  onSaved?: () => void;
}

export function SaveControlSetForm({
  siteId,
  positiveIds,
  negativeIds,
  recordType = "gene",
  onSaved,
}: SaveControlSetFormProps) {
  const [expanded, setExpanded] = useState(false);
  const [name, setName] = useState("");
  const [tags, setTags] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);

  const canSave = positiveIds.length > 0;

  const handleSave = useCallback(async () => {
    if (!name.trim() || !canSave) return;
    setSaving(true);
    try {
      await createControlSet({
        name: name.trim(),
        siteId,
        recordType,
        positiveIds,
        negativeIds,
        tags: tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        provenanceNotes: notes.trim() || undefined,
      });
      setSuccess(true);
      setTimeout(() => {
        setExpanded(false);
        setName("");
        setTags("");
        setNotes("");
        setSuccess(false);
        onSaved?.();
      }, 1500);
    } finally {
      setSaving(false);
    }
  }, [
    name,
    canSave,
    siteId,
    recordType,
    positiveIds,
    negativeIds,
    tags,
    notes,
    onSaved,
  ]);

  if (!expanded) {
    return (
      <button
        type="button"
        disabled={!canSave}
        onClick={() => setExpanded(true)}
        className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors duration-150 hover:text-foreground disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <Bookmark className="h-3 w-3" />
        Save as Control Set
      </button>
    );
  }

  if (success) {
    return (
      <p className="text-xs text-green-600 dark:text-green-400 animate-chip-in">
        Control set saved!
      </p>
    );
  }

  return (
    <div className="space-y-2 rounded-md border border-border p-3 animate-hover-card-in">
      <Input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Control set name"
        autoFocus
        className="h-7 bg-background px-2 text-xs"
      />
      <Input
        type="text"
        value={tags}
        onChange={(e) => setTags(e.target.value)}
        placeholder="Tags (comma-separated, optional)"
        className="h-7 bg-background px-2 text-xs text-muted-foreground"
      />
      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Notes (optional)"
        rows={2}
        className="w-full rounded-md border border-input bg-background px-2 py-1 text-xs text-muted-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
      />
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={handleSave} disabled={saving || !name.trim()}>
          {saving ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Bookmark className="h-3 w-3" />
          )}
          Save
        </Button>
        <button
          type="button"
          onClick={() => {
            setExpanded(false);
            setName("");
            setTags("");
            setNotes("");
          }}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          Cancel
        </button>
        <span className="ml-auto text-[10px] text-muted-foreground">
          {positiveIds.length}+ / {negativeIds.length}&minus;
        </span>
      </div>
    </div>
  );
}
