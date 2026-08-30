/**
 * The neutral a chart series paints when its token resolves to nothing, which
 * means the stylesheet did not load. Grey charts are a visible bug; charts in
 * the light palette on a dark ground are an invisible one.
 */
export const UNRESOLVED_SERIES_COLOR = "hsl(0 0% 50%)";
