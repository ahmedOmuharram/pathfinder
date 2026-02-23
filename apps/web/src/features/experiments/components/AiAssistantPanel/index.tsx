import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Sparkles, Send, Loader2, Wand2, ChevronDown } from "lucide-react";
import { streamAiAssist, type WizardStep, type AiAssistMessage } from "../../api";
import { listModels, type ModelCatalogResponse } from "@/lib/api/client";
import { PanelMessageContent } from "./PanelMessageContent";
import { ToolIndicator } from "./ToolIndicator";
import { STEP_LABELS, STEP_PLACEHOLDERS, QUICK_ACTION_PROMPTS } from "./constants";
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
    "text-[11px] [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_p]:break-words [&_code]:break-all [&_*]:max-w-full",
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

  const quickAction = QUICK_ACTION_PROMPTS[step];

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
    <div className="flex h-full flex-col border-l border-slate-200 bg-white">
      <div className="flex items-center border-b border-slate-200 px-3 py-2">
        <Sparkles className="h-3.5 w-3.5 text-amber-500" />
        <span className="ml-1.5 text-[11px] font-semibold text-slate-700">
          AI Assistant
        </span>
        <span className="ml-1 text-[10px] text-slate-400">— {STEP_LABELS[step]}</span>
      </div>

      <div className="flex items-center gap-2 border-b border-slate-100 px-3 py-1.5">
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowModelPicker(!showModelPicker)}
            className="flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-[10px] text-slate-600 transition hover:bg-slate-50"
          >
            {modelName}
            <ChevronDown className="h-2.5 w-2.5" />
          </button>
          {showModelPicker && modelCatalog && (
            <div className="absolute left-0 top-full z-10 mt-1 max-h-48 w-56 overflow-y-auto rounded-md border border-slate-200 bg-white shadow-lg">
              {modelCatalog.models.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => {
                    setSelectedModel(m.id);
                    setShowModelPicker(false);
                  }}
                  className={`flex w-full items-center px-3 py-1.5 text-left text-[11px] transition hover:bg-slate-50 ${
                    selectedModel === m.id
                      ? "bg-indigo-50 font-medium text-indigo-700"
                      : "text-slate-600"
                  }`}
                >
                  {m.name}
                  <span className="ml-auto text-[9px] text-slate-400">
                    {m.provider}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {quickAction && (
          <button
            type="button"
            onClick={() => sendMessage(quickAction.prompt)}
            disabled={streaming}
            className="flex items-center gap-1 rounded-md bg-amber-50 px-2.5 py-1 text-[10px] font-medium text-amber-700 transition hover:bg-amber-100 disabled:opacity-40"
          >
            <Wand2 className="h-3 w-3" />
            {quickAction.label}
          </button>
        )}
      </div>

      <div
        ref={scrollRef}
        className="min-h-0 min-w-0 flex-1 space-y-3 overflow-y-auto overflow-x-hidden px-3 py-3"
      >
        {messages.length === 0 && !streaming && (
          <div className="py-8 text-center">
            <Sparkles className="mx-auto mb-2 h-6 w-6 text-amber-300" />
            <div className="text-[11px] text-slate-500">
              Ask me anything about this step.
            </div>
            <div className="mt-1 text-[10px] text-slate-400">
              I can search the web, literature, and VEuPathDB catalogs.
            </div>
            {quickAction && (
              <button
                type="button"
                onClick={() => sendMessage(quickAction.prompt)}
                disabled={streaming}
                className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-amber-50 px-3 py-1.5 text-[11px] font-medium text-amber-700 transition hover:bg-amber-100"
              >
                <Wand2 className="h-3.5 w-3.5" />
                {quickAction.label}
              </button>
            )}
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`min-w-0 ${msg.role === "user" ? "ml-6 text-right" : "mr-6"}`}
          >
            {msg.role === "user" ? (
              <div className="inline-block max-w-full rounded-lg bg-indigo-600 px-3 py-2 text-[11px] leading-relaxed text-white">
                <div className="whitespace-pre-wrap break-words">{msg.content}</div>
              </div>
            ) : (
              <div className="min-w-0 max-w-full rounded-lg bg-slate-100 px-3 py-2 text-[11px] leading-relaxed text-slate-700">
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
              <div className="min-w-0 max-w-full rounded-lg bg-slate-100 px-3 py-2 text-[11px] leading-relaxed text-slate-700">
                <PanelMessageContent
                  content={streamText}
                  step={step}
                  {...contentProps}
                />
              </div>
            ) : (
              <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
                <Loader2 className="h-3 w-3 animate-spin" />
                Thinking...
              </div>
            )}
          </div>
        )}
      </div>

      <div className="border-t border-slate-200 p-3">
        <div className="flex gap-2">
          <input
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
            className="flex-1 rounded-md border border-slate-200 px-3 py-2 text-[12px] outline-none placeholder:text-slate-400 focus:border-indigo-300 disabled:opacity-50"
          />
          {streaming ? (
            <button
              type="button"
              onClick={cancel}
              className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[11px] font-medium text-red-600 transition hover:bg-red-100"
            >
              Stop
            </button>
          ) : (
            <button
              type="button"
              onClick={send}
              disabled={!input.trim()}
              className="flex items-center gap-1 rounded-md bg-indigo-600 px-3 py-2 text-[11px] font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Send className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
