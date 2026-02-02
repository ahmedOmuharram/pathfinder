import { useEffect } from "react";

export function useUndoRedoHotkeys(args: {
  enabled: boolean;
  tryUndoLocal: () => boolean;
  tryRedoLocal: () => boolean;
  canUndoGlobal: () => boolean;
  canRedoGlobal: () => boolean;
  undoGlobal: () => void;
  redoGlobal: () => void;
}) {
  const {
    enabled,
    tryUndoLocal,
    tryRedoLocal,
    canUndoGlobal,
    canRedoGlobal,
    undoGlobal,
    redoGlobal,
  } = args;

  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable)
      ) {
        return;
      }

      if (!(event.ctrlKey || event.metaKey)) return;
      const key = event.key.toLowerCase();
      if (key !== "z" && key !== "y") return;

      event.preventDefault();

      if (key === "y" || event.shiftKey) {
        if (tryRedoLocal()) return;
        if (canRedoGlobal()) redoGlobal();
        return;
      }

      if (tryUndoLocal()) return;
      if (canUndoGlobal()) undoGlobal();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    enabled,
    tryUndoLocal,
    tryRedoLocal,
    canUndoGlobal,
    canRedoGlobal,
    undoGlobal,
    redoGlobal,
  ]);
}

