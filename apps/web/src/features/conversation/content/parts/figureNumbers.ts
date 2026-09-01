import type { UIMessage } from "ai";
import type { EdaSubsetPreview, EdaViz } from "@pathfinder/shared";

const SUBSET_PREVIEW = "data-eda.subset-preview";
const VIZ = "data-eda.viz";

/** A part the thread numbers as a paper figure. */
type Plot = EdaSubsetPreview | EdaViz;

/** The thread's plots, in emission order. A subset preview is a plot only
 * when it carries a distribution to draw. */
function plotsOf(messages: readonly UIMessage[]): Plot[] {
  const plots: Plot[] = [];
  for (const message of messages) {
    for (const part of message.parts) {
      if (!("data" in part)) continue;
      if (part.type === VIZ) {
        plots.push(part.data as EdaViz);
        continue;
      }
      if (part.type !== SUBSET_PREVIEW) continue;
      const preview = part.data as EdaSubsetPreview;
      if (preview.distribution !== null) plots.push(preview);
    }
  }
  return plots;
}

/** The 1-based number of this plot among the thread's plots. Null when the
 * thread does not carry the payload. Two identical payloads tie on the
 * first. */
export function figureNumberFor(
  messages: readonly UIMessage[],
  data: Plot,
): number | null {
  const wanted = JSON.stringify(data);
  const index = plotsOf(messages).findIndex((plot) => JSON.stringify(plot) === wanted);
  return index === -1 ? null : index + 1;
}
