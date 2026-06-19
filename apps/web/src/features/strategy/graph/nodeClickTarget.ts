export function isNodeToolbarOrMenuTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.closest("[data-node-toolbar]") != null ||
    target.closest('[role="menu"]') != null
  );
}
