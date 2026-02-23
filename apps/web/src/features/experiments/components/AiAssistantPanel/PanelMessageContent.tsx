import { useMemo } from "react";
import { ChatMarkdown } from "@/features/chat/components/ChatMarkdown";
import {
  parseSuggestions,
  type SuggestionSegment,
  type SearchSuggestion,
  type RunConfigSuggestion,
} from "../../suggestionParser";
import type { WizardStep } from "../../api";
import {
  PanelSuggestionCard,
  PanelGeneCard,
  PanelParamCard,
  PanelRunConfigCard,
} from "./PanelCards";

export function PanelMessageContent({
  content,
  step: _step,
  onSearchApply,
  onGeneAdd,
  addedGeneIds,
  onParamsApply,
  onRunConfigApply,
  className,
}: {
  content: string;
  step: WizardStep;
  onSearchApply?: (s: SearchSuggestion) => void;
  onGeneAdd?: (geneId: string, role: "positive" | "negative") => void;
  addedGeneIds?: Set<string>;
  onParamsApply?: (params: Record<string, string>) => void;
  onRunConfigApply?: (config: RunConfigSuggestion) => void;
  className?: string;
}) {
  const segments = useMemo(() => parseSuggestions(content), [content]);
  const hasCards = segments.some((s: SuggestionSegment) => s.type !== "text");

  if (!hasCards) {
    return <ChatMarkdown content={content} className={className} />;
  }

  return (
    <>
      {segments.map((seg, i) => {
        if (seg.type === "text") {
          const trimmed = seg.content.trim();
          if (!trimmed) return null;
          return <ChatMarkdown key={i} content={trimmed} className={className} />;
        }
        if (seg.type === "suggestion") {
          return (
            <PanelSuggestionCard key={i} data={seg.data} onApply={onSearchApply} />
          );
        }
        if (seg.type === "control_gene") {
          return (
            <PanelGeneCard
              key={i}
              data={seg.data}
              isAdded={addedGeneIds?.has(seg.data.geneId) ?? false}
              onAdd={onGeneAdd}
            />
          );
        }
        if (seg.type === "param_suggestion") {
          return <PanelParamCard key={i} data={seg.data} onApply={onParamsApply} />;
        }
        if (seg.type === "run_config") {
          return (
            <PanelRunConfigCard key={i} data={seg.data} onApply={onRunConfigApply} />
          );
        }
        return null;
      })}
    </>
  );
}
