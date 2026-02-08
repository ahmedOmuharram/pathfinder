import { useEffect } from "react";

export function useDraftDetailsInputs(args: {
  isDraftView: boolean;
  draftName: string | undefined | null;
  draftDescription: string | undefined | null;
  setNameValue: (value: string) => void;
  setDescriptionValue: (value: string) => void;
}) {
  const {
    isDraftView,
    draftName,
    draftDescription,
    setNameValue,
    setDescriptionValue,
  } = args;

  useEffect(() => {
    if (!isDraftView) return;
    setNameValue(draftName || "Draft Strategy");
    setDescriptionValue(draftDescription || "");
  }, [isDraftView, draftName, draftDescription, setNameValue, setDescriptionValue]);
}
