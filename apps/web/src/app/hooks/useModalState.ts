import { useState } from "react";

interface ModalState {
  showSettings: boolean;
  openSettings: () => void;
  closeSettings: () => void;

  graphEditing: boolean;
  openGraphEditor: () => void;
  closeGraphEditor: () => void;
}

export function useModalState(): ModalState {
  const [showSettings, setShowSettings] = useState(false);
  const [graphEditing, setGraphEditing] = useState(false);

  const openSettings = () => setShowSettings(true);
  const closeSettings = () => setShowSettings(false);
  const openGraphEditor = () => setGraphEditing(true);
  const closeGraphEditor = () => setGraphEditing(false);

  return {
    showSettings,
    openSettings,
    closeSettings,
    graphEditing,
    openGraphEditor,
    closeGraphEditor,
  };
}
