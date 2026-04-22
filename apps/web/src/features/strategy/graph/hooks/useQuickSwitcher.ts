"use client";

import { useState } from "react";

export interface QuickSwitcherState {
  open: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;
}

export function useQuickSwitcher(): QuickSwitcherState {
  const [open, setOpen] = useState(false);
  const toggle = (): void => {
    setOpen((prev) => !prev);
  };
  return { open, setOpen, toggle };
}
