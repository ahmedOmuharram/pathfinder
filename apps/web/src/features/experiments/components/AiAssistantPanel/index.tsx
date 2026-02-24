import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Sparkles, Send, Loader2, Wand2, ChevronDown } from "lucide-react";
import { streamAiAssist, type WizardStep, type AiAssistMessage } from "../../api";
import { listModels, type ModelCatalogResponse } from "@/lib/api/client";
import { Button } from "@/lib/components/ui/Button";
import { Input } from "@/lib/components/ui/Input";
import { cn } from "@/lib/utils/cn";
import { PanelMessageContent } from "./PanelMessageContent";
import { ToolIndicator } from "./ToolIndicator";
import {
  STEP_LABELS,
  STEP_PLACEHOLDERS,
  QUICK_ACTION_PROMPTS,
  type QuickAction,
} from "./constants";
import type { SearchSuggestion, RunConfigSuggestion } from "../../suggestionParser";

interface AiAssistantPanelProps {
  siteId: string;
  step: WizardStep;
  context: Record<string, unknown>;
  onSuggestionApply?: (suggestion: SearchSuggestion) => void;
  onGeneAdd?: (geneId: string, role: "positive" | "negative") => void;
  onParamsApply?: (params: Record<string, string>) => void;
  onRunConfigApply?: (config: RunConfigSuggestion) => void;
}

const contentPropsDefaults = {
  className:
    "text-xs [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_p]:break-words [&_code]:break-all [&_*]:max-w-full",
};

export function AiAssistantPanel({
  siteId,
  step,
  context,
  onSuggestionApply,
  onGeneAdd,
  onParamsApply,
  onRunConfigApply,
}: AiAssistantPanelProps) {
  const [messages, setMessages] = useState<AiAssistMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [activeTools, setActiveTools] = useState<Set<string>>(new Set());
  const [completedTools, setCompletedTools] = useState<Set<string>>(new Set());
  const [selectedModel, setSelectedModel] = useState("openai/gpt-4o");
  const [modelCatalog, setModelCatalog] = useState<ModelCatalogResponse | null>(null);
  const [showModelPicker, setShowModelPicker] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const addedGeneIds = useMemo(() => {
    const ids = new Set<string>();
    const pos = context.positiveControls;
    const neg = context.negativeControls;
    if (Array.isArray(pos)) pos.forEach((id) => typeof id === "string" && ids.add(id));
    if (Array.isArray(neg)) neg.forEach((id) => typeof id === "string" && ids.add(id));
    return ids;
  }, [context.positiveControls, context.negativeControls]);

  useEffect(() => {
    listModels()
      .then(setModelCatalog)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamText]);

  const sendMessage = useCallback(
    (text: string) => {
      if (!text.trim() || streaming) return;

      const userMsg: AiAssistMessage = { role: "user", content: text.trim() };
      const updatedHistory = [...messages, userMsg];
      setMessages(updatedHistory);
      setInput("");
      setStreaming(true);
      setStreamText("");
      setActiveTools(new Set());
      setCompletedTools(new Set());

      abortRef.current = streamAiAssist(
        {
          siteId,
          step,
          message: text.trim(),
          context,
          history: updatedHistory.slice(0, -1),
          model: selectedModel,
        },
        {
          onDelta: (delta) => setStreamText((prev) => prev + delta),
          onToolCall: (name, status) => {
            if (status === "start") {
              setActiveTools((prev) => new Set([...prev, name]));
            } else {
              setActiveTools((prev) => {
                const next = new Set(prev);
                next.delete(name);
                return next;
              });
              setCompletedTools((prev) => new Set([...prev, name]));
            }
          },
          onComplete: (fullText) => {
            setMessages((prev) => [...prev, { role: "assistant", content: fullText }]);
            setStreamText("");
            setStreaming(false);
            setActiveTools(new Set());
          },
          onError: (error) => {
            setMessages((prev) => [
              ...prev,
              { role: "assistant", content: `Error: ${error}` },
            ]);
            setStreamText("");
            setStreaming(false);
            setActiveTools(new Set());
          },
        },
      );
    },
    [streaming, messages, siteId, step, context, selectedModel],
  );

  const send = useCallback(() => sendMessage(input), [sendMessage, input]);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    if (streamText) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: streamText + " [cancelled]" },
      ]);
    }
    setStreamText("");
    setStreaming(false);
    setActiveTools(new Set());
  }, [streamText]);

  const rawQuickAction = QUICK_ACTION_PROMPTS[step];
  const quickActions: QuickAction[] = rawQuickAction
    ? Array.isArray(rawQuickAction)
      ? rawQuickAction
      : [rawQuickAction]
    : [];

  const modelName =
    modelCatalog?.models.find((m) => m.id === selectedModel)?.name ??
    selectedModel.split("/").pop() ??
    "Model";

  const contentProps = {
    onSearchApply: onSuggestionApply,
    onGeneAdd,
    addedGeneIds,
    onParamsApply,
    onRunConfigApply,
    ...contentPropsDefaults,
  };

  return (
    <div className="flex h-full flex-col border-l border-border bg-card">
      <div className="flex items-center border-b border-border px-3 py-2.5">
        <Sparkles className="h-4 w-4 text-warning" />
        <span className="ml-1.5 text-sm font-semibold text-foreground">
          AI Assistant
        </span>
        <span className="ml-1.5 text-xs text-muted-foreground">
          {STEP_LABELS[step]}
        </span>
      </div>

      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowModelPicker(!showModelPicker)}
            className="flex items-center gap-1 rounded-md border border-input px-2 py-1 text-xs text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-accent-foreground"
          >
            {modelName}
            <ChevronDown className="h-3 w-3" />
          </button>
          {showModelPicker && modelCatalog && (
            <div className="absolute left-0 top-full z-10 mt-1 max-h-48 w-56 overflow-y-auto rounded-lg border border-border bg-popover shadow-lg animate-scale-in">
              {modelCatalog.models.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => {
                    setSelectedModel(m.id);
                    setShowModelPicker(false);
                  }}
                  className={cn(
                    "flex w-full items-center px-3 py-1.5 text-left text-xs transition-colors duration-150 hover:bg-accent",
                    selectedModel === m.id
                      ? "bg-primary/5 font-medium text-primary"
                      : "text-popover-foreground",
                  )}
                >
                  {m.name}
                  <span className="ml-auto text-xs text-muted-foreground">
                    {m.provider}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {quickActions.map((qa) => (
          <Button
            key={qa.label}
            variant="outline"
            size="sm"
            onClick={() => sendMessage(qa.prompt)}
            disabled={streaming}
            className="text-xs"
          >
            <Wand2 className="h-3 w-3" />
            {qa.label}
          </Button>
        ))}
      </div>

      <div
        ref={scrollRef}
        className="min-h-0 min-w-0 flex-1 space-y-3 overflow-y-auto overflow-x-hidden px-3 py-3"
      >
        {messages.length === 0 && !streaming && (
          <div className="py-8 text-center animate-fade-in">
            <Sparkles className="mx-auto mb-2 h-6 w-6 text-warning/50" />
            <div className="text-sm text-muted-foreground">
              Context-aware guidance from literature and VEuPathDB catalogs.
            </div>
            {quickActions.length > 0 && (
              <div className="mt-3 flex flex-wrap justify-center gap-2">
                {quickActions.map((qa) => (
                  <Button
                    key={qa.label}
                    variant="outline"
                    size="sm"
                    onClick={() => sendMessage(qa.prompt)}
                    disabled={streaming}
                  >
                    <Wand2 className="h-3.5 w-3.5" />
                    {qa.label}
                  </Button>
                ))}
              </div>
            )}
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`min-w-0 ${msg.role === "user" ? "ml-6 text-right" : "mr-6"}`}
          >
            {msg.role === "user" ? (
              <div className="inline-block max-w-full rounded-lg bg-primary px-3 py-2 text-xs leading-relaxed text-primary-foreground">
                <div className="whitespace-pre-wrap break-words">{msg.content}</div>
              </div>
            ) : (
              <div className="min-w-0 max-w-full rounded-lg bg-muted px-3 py-2 text-xs leading-relaxed text-foreground">
                <PanelMessageContent
                  content={msg.content}
                  step={step}
                  {...contentProps}
                />
              </div>
            )}
          </div>
        ))}

        {streaming && (
          <div className="mr-6">
            {(activeTools.size > 0 || completedTools.size > 0) && (
              <div className="mb-1.5 flex flex-wrap gap-1">
                {Array.from(activeTools).map((name) => (
                  <ToolIndicator key={name} name={name} active />
                ))}
                {Array.from(completedTools)
                  .filter((n) => !activeTools.has(n))
                  .map((name) => (
                    <ToolIndicator key={name} name={name} active={false} />
                  ))}
              </div>
            )}
            {streamText ? (
              <div className="min-w-0 max-w-full rounded-lg bg-muted px-3 py-2 text-xs leading-relaxed text-foreground">
                <PanelMessageContent
                  content={streamText}
                  step={step}
                  {...contentProps}
                />
              </div>
            ) : (
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" />
                Thinking...
              </div>
            )}
          </div>
        )}
      </div>

      <div className="border-t border-border p-3">
        <div className="flex gap-2">
          <Input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder={STEP_PLACEHOLDERS[step]}
            disabled={streaming}
            className="flex-1"
          />
          {streaming ? (
            <Button variant="destructive" size="sm" onClick={cancel}>
              Stop
            </Button>
          ) : (
            <Button size="icon" onClick={send} disabled={!input.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
