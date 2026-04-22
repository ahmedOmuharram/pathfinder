export const FADE_IN_UP = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.2, ease: "easeOut" },
} as const;

export const SHEET_SPRING = {
  type: "spring",
  stiffness: 380,
  damping: 36,
} as const;

export const POP_IN = {
  initial: { scale: 0.8, opacity: 0 },
  animate: { scale: 1, opacity: 1 },
  transition: { duration: 0.18, ease: "backOut" },
} as const;

export const PATH_MORPH = {
  duration: 0.3,
  ease: [0.4, 0, 0.2, 1],
} as const;

export const LAYOUT_SPRING = {
  type: "spring",
  stiffness: 300,
  damping: 30,
} as const;

export const CROSSFADE = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  transition: { duration: 0.15 },
} as const;

export const REDUCED_INSTANT = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  transition: { duration: 0.15 },
} as const;

export const STAGGER_DELAY_MS = 80;
export const EDGE_DRAW_DURATION_MS = 400;
