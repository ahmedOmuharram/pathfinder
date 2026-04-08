import { useState } from "react";

interface ModalState {
  showSettings: boolean;
  openSettings: () => void;
  closeSettings: () => void;

  showEngine: boolean;
  openEngine: () => void;
  closeEngine: () => void;

  graphEditing: boolean;
  openGraphEditor: () => void;
  closeGraphEditor: () => void;
}

export function useModalState(): ModalState {
  const [showSettings, setShowSettings] = useState(false);
  const [showEngine, setShowEngine] = useState(false);
  const [graphEditing, setGraphEditing] = useState(false);

  const openSettings = () => setShowSettings(true);
  const closeSettings = () => setShowSettings(false);
  const openEngine = () => setShowEngine(true);
  const closeEngine = () => setShowEngine(false);
  const openGraphEditor = () => setGraphEditing(true);
  const closeGraphEditor = () => setGraphEditing(false);

  return {
    showSettings,
    openSettings,
    closeSettings,
    showEngine,
    openEngine,
    closeEngine,
    graphEditing,
    openGraphEditor,
    closeGraphEditor,
  };
}
