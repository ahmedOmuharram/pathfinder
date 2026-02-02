import { useEffect } from "react";

export function useBeforeUnloadUnsaved(isUnsaved: boolean) {
  useEffect(() => {
    if (!isUnsaved) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isUnsaved]);
}

