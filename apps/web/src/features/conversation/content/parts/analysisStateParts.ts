import type { UIMessage } from "ai";
import type { EdaAnalysisState } from "@pathfinder/shared";

const PART_TYPE = "data-eda.analysis-state";

function statePartsOf(messages: readonly UIMessage[]): EdaAnalysisState[] {
  const states: EdaAnalysisState[] = [];
  for (const message of messages) {
    for (const part of message.parts) {
      if (part.type !== PART_TYPE || !("data" in part)) continue;
      states.push(part.data as EdaAnalysisState);
    }
  }
  return states;
}

/** Whether this payload is the thread's newest state for its analysis. */
export function isNewestAnalysisState(
  messages: readonly UIMessage[],
  data: EdaAnalysisState,
): boolean {
  const mine = statePartsOf(messages).filter(
    (state) => state.analysisId === data.analysisId,
  );
  const last = mine.at(-1);
  if (last === undefined) return true;
  return JSON.stringify(last) === JSON.stringify(data);
}

/** The study's display name for one analysis, read off the thread. */
export function studyNameFor(
  messages: readonly UIMessage[],
  analysisId: string,
): string {
  const mine = statePartsOf(messages).filter(
    (state) => state.analysisId === analysisId,
  );
  return mine.at(-1)?.studyDisplayName ?? "";
}
