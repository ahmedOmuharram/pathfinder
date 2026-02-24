import suggestedQuestions from "@/features/chat/data/suggestedQuestions.json";
import { isRecord } from "@/lib/utils/isRecord";

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
  const { isCompact, siteId, displayName, onSend, isStreaming, hasMessages } = props;

  if (hasMessages || isStreaming) return null;

  const suggestions = _suggestionsForSite(suggestedQuestions, siteId);

  return (
    <div className="flex flex-col items-center justify-center h-full text-center animate-fade-in">
      <h2
        className={`mb-1 font-semibold tracking-tight text-foreground ${
          isCompact ? "text-base" : "text-lg"
        }`}
      >
        {displayName}
      </h2>
      <p
        className={`max-w-md text-muted-foreground text-sm leading-relaxed ${isCompact ? "mb-4" : "mb-6"}`}
      >
        Build and refine multi-step VEuPathDB search strategies with guided parameter
        selection and validation.
      </p>
      <div className="grid max-w-lg grid-cols-1 gap-2 text-left">
        {suggestions.map((suggestion: string, i: number) => (
          <button
            key={i}
            onClick={() => onSend(suggestion)}
            className="rounded-lg border border-border bg-card px-4 py-3 text-left text-sm text-foreground shadow-xs transition-all duration-150 hover:border-ring/30 hover:shadow-sm hover:-translate-y-px active:translate-y-0"
          >
            &ldquo;{suggestion}&rdquo;
          </button>
        ))}
      </div>
    </div>
  );
}
