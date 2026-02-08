import suggestedQuestions from "@/data/suggestedQuestions.json";
import type { ChatMode } from "@pathfinder/shared";

type SuggestedQuestionsData = Record<
  string,
  Record<ChatMode, string[]> | string[] | undefined
>;

function _suggestionsForSite(
  all: SuggestedQuestionsData | unknown,
  options: { siteId: string; mode: ChatMode },
): string[] {
  const { siteId, mode } = options;
  if (!all || typeof all !== "object" || Array.isArray(all)) return [];
  const bySiteRecord = all as SuggestedQuestionsData;
  const bySite = bySiteRecord[siteId] ?? bySiteRecord.plasmodb;

  if (!bySite) return [];

  // Preferred shape: { plan: string[], execute: string[] }
  if (typeof bySite === "object" && !Array.isArray(bySite)) {
    const modeValue = (bySite as Record<string, unknown>)[mode];
    if (Array.isArray(modeValue) && modeValue.every((v) => typeof v === "string")) {
      return modeValue;
    }
  }

  // Fallback shape: string[]
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
  mode: ChatMode;
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
    mode,
    onSend,
    isStreaming,
    hasMessages,
  } = props;

  if (hasMessages || isStreaming) return null;

  const suggestions = _suggestionsForSite(suggestedQuestions, { siteId, mode });

  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <h2
        className={`mb-2 font-semibold text-slate-900 ${
          isCompact ? "text-sm" : "text-base"
        }`}
      >
        {mode === "plan"
          ? signedIn && firstName
            ? `Welcome, ${firstName}. Ready to plan a strategy?`
            : `Ready to plan a strategy?`
          : signedIn && firstName
            ? `Welcome, ${firstName}. Ready to create strategies?`
            : `Ready to create strategies?`}
      </h2>
      <p className={`max-w-md text-slate-500 ${isCompact ? "mb-3" : "mb-6"}`}>
        {mode === "plan"
          ? `Describe your goal and I’ll propose a concrete, executable plan for ${displayName} (steps, operators, and key parameters).`
          : `Ask me to build a VEuPathDB search strategy for ${displayName}. I can help you find records, combine results, and explore your data.`}
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
