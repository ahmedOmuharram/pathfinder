"use client";

import { useState } from "react";

import type { UserQuestion, QuestionOption } from "@/lib/types/plan";

interface PlanQuestionCardProps {
  question: UserQuestion;
  onAnswer: (questionId: string, answer: unknown) => void;
  disabled: boolean;
}

function OptionButton({
  option,
  selected,
  onSelect,
  disabled,
}: {
  option: QuestionOption;
  selected: boolean;
  onSelect: () => void;
  disabled: boolean;
}) {
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);

  const showDetails = hovered || focused || selected;

  return (
    <div className="space-y-1">
      <button
        type="button"
        disabled={disabled}
        onClick={onSelect}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        aria-expanded={showDetails}
        className={`flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-xs transition-colors ${
          selected
            ? "border-purple-500/50 bg-purple-500/10 text-foreground"
            : "border-border bg-card text-foreground hover:bg-accent"
        } ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}
      >
        <span
          className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${
            selected
              ? "border-purple-500 bg-purple-500"
              : "border-muted-foreground/40"
          }`}
        >
          {selected && (
            <span className="h-1.5 w-1.5 rounded-full bg-white" />
          )}
        </span>
        <span className="flex-1">
          <span className="font-medium">{option.label}</span>
          {option.recommended && (
            <span className="ml-2 rounded-full bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-medium leading-none text-emerald-400">
              Recommended
            </span>
          )}
        </span>
      </button>

      {/* Description + pros/cons — shown on hover, focus, or when selected */}
      {showDetails && (
        <div className="ml-6 space-y-1 rounded-md bg-muted/50 px-2 py-1.5">
          <p className="text-[11px] leading-snug text-muted-foreground">
            {option.description}
          </p>
          {option.pros.length > 0 && (
            <div className="text-[11px] text-muted-foreground">
              <span className="font-medium text-emerald-400">Pros:</span>{" "}
              {option.pros.join(", ")}
            </div>
          )}
          {option.cons.length > 0 && (
            <div className="text-[11px] text-muted-foreground">
              <span className="font-medium text-red-400">Cons:</span>{" "}
              {option.cons.join(", ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function PlanQuestionCard({ question, onAnswer, disabled }: PlanQuestionCardProps) {
  const [selectedOption, setSelectedOption] = useState<string | null>(
    question.answer != null ? String(question.answer) : null,
  );
  const [textAnswer, setTextAnswer] = useState<string>(
    question.answer != null ? String(question.answer) : "",
  );

  const hasOptions = question.options !== null && question.options.length > 0;

  const isAnswered = question.answer != null;

  function handleOptionSelect(label: string) {
    setSelectedOption(label);
  }

  function handleOptionSubmit() {
    if (selectedOption != null) {
      onAnswer(question.id, selectedOption);
    }
  }

  function handleTextSubmit() {
    if (textAnswer.trim() !== "") {
      onAnswer(question.id, textAnswer.trim());
    }
  }

  return (
    <div className="rounded-md border border-yellow-500/30 bg-yellow-500/5 px-3 py-2 space-y-2">
      {/* Question text */}
      <p className="text-sm font-medium text-foreground">{question.question}</p>

      {/* Context */}
      {question.context !== "" && (
        <p className="text-[11px] leading-snug text-muted-foreground">{question.context}</p>
      )}

      {/* Options or text input */}
      {hasOptions ? (
        <div className="space-y-1.5">
          {question.options!.map((opt) => (
            <OptionButton
              key={opt.label}
              option={opt}
              selected={selectedOption === opt.label}
              onSelect={() => handleOptionSelect(opt.label)}
              disabled={disabled || isAnswered}
            />
          ))}
          <button
            type="button"
            disabled={disabled || selectedOption == null}
            onClick={handleOptionSubmit}
            className="rounded-md border border-border bg-card px-2 py-1 text-xs text-foreground transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            Submit
          </button>
        </div>
      ) : (
        <div className="flex gap-2">
          <input
            type="text"
            value={textAnswer}
            disabled={disabled}
            onChange={(e) => setTextAnswer(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleTextSubmit();
            }}
            placeholder="Type your answer..."
            className="flex-1 rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
          />
          <button
            type="button"
            disabled={disabled || textAnswer.trim() === ""}
            onClick={handleTextSubmit}
            className="rounded-md border border-border bg-card px-2 py-1 text-xs text-foreground transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            Submit
          </button>
        </div>
      )}
    </div>
  );
}
