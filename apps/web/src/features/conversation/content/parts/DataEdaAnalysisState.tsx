"use client";

import { useRouter } from "next/navigation";
import type { EdaAnalysisState, EdaEntityCount } from "@pathfinder/shared";

import { Button } from "@/components/ui/button";
import { useConversationId } from "@/lib/hooks/useConversationId";
import { edaTabUrl } from "@/lib/routes";
import { useHydrateEdaPart } from "@/state/eda";

const MUTED = "text-[11px] text-muted-foreground";

export function DataEdaAnalysisState({ data }: { data: EdaAnalysisState }) {
  useHydrateEdaPart({ kind: "analysis-state", data });
  const conversationId = useConversationId();
  const hiddenFilters = data.numFilters - data.filterSummaries.length;

  return (
    <div
      data-testid="data-eda-analysis-state"
      className="my-2 rounded-md border border-border bg-card px-3 py-2 text-xs"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <span className="font-medium text-foreground">
            {data.studyDisplayName.length > 0 ? data.studyDisplayName : data.datasetId}
          </span>
          <div className={MUTED}>{data.displayName}</div>
        </div>
        {conversationId !== null ? (
          <OpenEdaTab siteId={data.siteId} conversationId={conversationId} />
        ) : null}
      </div>

      {data.filterSummaries.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {data.filterSummaries.map((summary, index) => (
            <span
              key={index}
              data-testid={`data-eda-filter-chip-${String(index)}`}
              className="rounded-full border border-border px-2 py-0.5 text-[11px]"
            >
              {summary}
            </span>
          ))}
        </div>
      ) : (
        <div className={`mt-2 ${MUTED}`}>No filters yet</div>
      )}
      {hiddenFilters > 0 ? (
        <div data-testid="data-eda-filter-overflow" className={`mt-1 ${MUTED}`}>
          {`${hiddenFilters.toLocaleString()} more ${hiddenFilters === 1 ? "filter" : "filters"}`}
        </div>
      ) : null}

      <ul className={`mt-2 ${MUTED}`}>
        {data.entityCounts.map((entity) => (
          <li key={entity.entityId}>{entityCountLine(entity)}</li>
        ))}
      </ul>
      <div className={`mt-1 ${MUTED}`}>
        {`${data.numComputations.toLocaleString()} ${data.numComputations === 1 ? "computation" : "computations"}`}
      </div>
    </div>
  );
}

function entityCountLine(entity: EdaEntityCount): string {
  const name =
    entity.entityDisplayName.length > 0 ? entity.entityDisplayName : entity.entityId;
  return `${entity.count.toLocaleString()} of ${entity.unfilteredCount.toLocaleString()} ${name}`;
}

function OpenEdaTab({
  siteId,
  conversationId,
}: {
  siteId: string;
  conversationId: string;
}) {
  const router = useRouter();
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="h-7 shrink-0 px-2 text-xs"
      onClick={() => router.push(edaTabUrl(siteId, conversationId))}
    >
      Open in EDA tab
    </Button>
  );
}
