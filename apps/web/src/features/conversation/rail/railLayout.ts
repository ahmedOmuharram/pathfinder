/** Widths of the fixed columns beside the chat, in CSS pixels. */
export const NAV_RAIL_WIDTH = 44;
export const RAIL_ICON_STRIP_WIDTH = 44;
export const RAIL_PANEL_WIDTH = 360;
export const CONVERSATION_LIST_WIDTH = 360;
export const LIST_RESIZE_HANDLE_WIDTH = 4;

/** Narrower than this the chat column is a sliver, so a panel overlays it. */
export const MIN_CHAT_COLUMN_WIDTH = 420;

export interface RailLayoutInput {
  viewportWidth: number;
  listExpanded: boolean;
  panelOpen: boolean;
}

/** What the chat column keeps when every open column takes its share. */
export function chatColumnWidth({
  viewportWidth,
  listExpanded,
  panelOpen,
}: RailLayoutInput): number {
  const list = listExpanded ? CONVERSATION_LIST_WIDTH + LIST_RESIZE_HANDLE_WIDTH : 0;
  const panel = panelOpen ? RAIL_PANEL_WIDTH : 0;
  return viewportWidth - NAV_RAIL_WIDTH - list - RAIL_ICON_STRIP_WIDTH - panel;
}

/**
 * Whether the open rail panel floats over the chat instead of squeezing it.
 * A width the server cannot know keeps the panel in flow until the page
 * measures itself.
 */
export function shouldOverlayRailPanel(input: RailLayoutInput): boolean {
  if (!input.panelOpen) return false;
  const chat = chatColumnWidth(input);
  if (!Number.isFinite(chat)) return false;
  return chat < MIN_CHAT_COLUMN_WIDTH;
}
