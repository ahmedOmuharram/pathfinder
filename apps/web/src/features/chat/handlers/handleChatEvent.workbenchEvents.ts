import type { OptionalCallbacks } from "./handleChatEvent.types";
import type { WorkbenchGeneSetData } from "@/lib/sse_events";

/**
 * Handle `workbench_gene_set` events -- AI created a gene set in the workbench.
 *
 * Delegates to the `onWorkbenchGeneSet` callback provided via ChatEventContext
 * so this handler does not depend on the workbench store directly.
 */
export function handleWorkbenchGeneSetEvent(
  ctx: OptionalCallbacks,
  data: WorkbenchGeneSetData,
) {
  const gs = data.geneSet;
  if (gs?.id == null || gs.name == null || gs.geneCount == null || gs.source == null || gs.siteId == null) return;

  ctx.onWorkbenchGeneSet?.({
    id: gs.id,
    name: gs.name,
    geneCount: gs.geneCount,
    source: gs.source,
    siteId: gs.siteId,
  });
}
