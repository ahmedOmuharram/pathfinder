import suggestedQuestions from "@/data/suggestedQuestions.json";
import { isRecord } from "@/shared/utils/isRecord";

type SuggestedQuestionsData = Record<string, string[] | undefined>;

function _suggestionsForSite(
  all: SuggestedQuestionsData | unknown,
  siteId: string,
): string[] {
  if (!isRecord(all)) return [];
  const bySite =
    (all as SuggestedQuestionsData)[siteId] ?? (all as SuggestedQuestionsData).plasmodb;
  if (Array.isArray(bySite) && bySite.every((v) => typeof v === "string")) {
    return bySite;
  }
  return [];
}

export function ChatEmptyState(props: {
  isCompact: boolean;
  siteId: string;
  displayName: string;
  firstName: string | undefined;
  signedIn: boolean;
  onSend: (message: string) => void;
  isStreaming: boolean;
  hasMessages: boolean;
}) {
  const {
    isCompact,
    siteId,
    displayName,
    firstName,
    signedIn,
    onSend,
    isStreaming,
    hasMessages,
  } = props;

  if (hasMessages || isStreaming) return null;

  const suggestions = _suggestionsForSite(suggestedQuestions, siteId);

  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <h2
        className={`mb-2 font-semibold text-slate-900 ${
          isCompact ? "text-sm" : "text-base"
        }`}
      >
        {signedIn && firstName
          ? `Welcome, ${firstName}. Ready to explore ${displayName}?`
          : `Ready to explore ${displayName}?`}
      </h2>
      <p className={`max-w-md text-slate-500 ${isCompact ? "mb-3" : "mb-6"}`}>
        {`Describe your research question and I'll help you build a VEuPathDB search strategy for ${displayName} — from planning the approach to executing and refining the results.`}
      </p>
      <div className="grid max-w-lg grid-cols-1 gap-3 text-left">
        {suggestions.map((suggestion: string, i: number) => (
          <button
            key={i}
            onClick={() => onSend(suggestion)}
            className={`rounded-md border border-slate-200 bg-white px-3 py-2 text-left text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50 ${
              isCompact ? "text-[11px]" : "text-[13px]"
            }`}
          >
            &ldquo;{suggestion}&rdquo;
          </button>
        ))}
      </div>
    </div>
  );
}
