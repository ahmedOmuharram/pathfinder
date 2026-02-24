import { useState, useRef, useCallback } from "react";
import { updateExperimentNotes } from "../../api";

interface NotesEditorProps {
  experimentId: string;
  initialNotes: string;
}

export function NotesEditor({ experimentId, initialNotes }: NotesEditorProps) {
  const [notes, setNotes] = useState(initialNotes);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const persist = useCallback(
    (value: string) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        updateExperimentNotes(experimentId, value).catch(() => {});
      }, 800);
    },
    [experimentId],
  );

  return (
    <textarea
      value={notes}
      onChange={(e) => {
        setNotes(e.target.value);
        persist(e.target.value);
      }}
      placeholder="Add notes about this experiment..."
      rows={2}
      className="w-full resize-none rounded-lg border border-border bg-card px-4 py-2.5 text-xs text-muted-foreground outline-none placeholder:text-muted-foreground transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring"
    />
  );
}
