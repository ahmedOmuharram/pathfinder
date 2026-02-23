import { useEffect, useState } from "react";

/**
 * Return the value from the previous render.
 *
 * On the first render the hook returns ``undefined``.  After every
 * subsequent render it returns the value that was passed during the
 * **previous** render, making it easy to detect prop/state changes
 * inside effects without manually juggling refs.
 *
 * Uses state instead of ref for the return value to satisfy React's
 * rule against accessing refs during render.
 *
 * :param value: The value to track across renders.
 * :returns: The value from the previous render, or ``undefined``.
 */
export function usePrevious<T>(value: T): T | undefined {
  const [previous, setPrevious] = useState<T | undefined>(undefined);
  useEffect(() => {
    setPrevious(value);
  }, [value]);
  return previous;
}
