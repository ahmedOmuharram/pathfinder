"use client";

import { AnimatePresence, motion } from "motion/react";
import { X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";

import type {
  Command,
  CommandContext,
  ParamDef,
  ParamValues,
  SelectOption,
} from "./types";

export interface ParamStepperProps {
  open: boolean;
  command: Command | null;
  ctx: CommandContext;
  onComplete: (values: ParamValues) => void;
  onCancel: () => void;
}

export function ParamStepper({
  open,
  command,
  ctx,
  onComplete,
  onCancel,
}: ParamStepperProps) {
  const [stepIdx, setStepIdx] = useState(0);
  const [values, setValues] = useState<ParamValues>({});

  useEffect(() => {
    if (!open) {
      setStepIdx(0);
      setValues({});
    }
  }, [open]);

  if (!open || command === null) return null;
  if (command.params.length === 0) return null;

  const param = command.params[stepIdx];
  if (param === undefined) return null;

  const isLast = stepIdx === command.params.length - 1;

  const next = (value: string) => {
    const merged = { ...values, [param.name]: value };
    setValues(merged);
    if (isLast) {
      onComplete(merged);
    } else {
      setStepIdx(stepIdx + 1);
    }
  };

  return (
    <AnimatePresence>
      <motion.div
        key="param-stepper"
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 6 }}
        transition={{ duration: 0.15 }}
        data-testid="slash-param-stepper"
        className={cn(
          "absolute bottom-full left-0 right-0 z-20 mb-2",
          "rounded-lg border border-border bg-popover",
          "shadow-[var(--shadow-float)]",
        )}
      >
        <div className="flex items-center justify-between border-b border-border/60 px-3 py-2">
          <div className="flex items-center gap-2 text-xs">
            <span className="font-mono font-medium text-foreground">
              /{command.name}
            </span>
            <span className="text-muted-foreground">
              step {stepIdx + 1} / {command.params.length}
            </span>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            onClick={onCancel}
            aria-label="Cancel"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
        <ParamRow param={param} ctx={ctx} onSubmit={next} />
      </motion.div>
    </AnimatePresence>
  );
}

function ParamRow({
  param,
  ctx,
  onSubmit,
}: {
  param: ParamDef;
  ctx: CommandContext;
  onSubmit: (value: string) => void;
}) {
  if (param.kind === "select") {
    return <SelectRow param={param} ctx={ctx} onSubmit={onSubmit} />;
  }
  if (param.kind === "textarea") {
    return <TextAreaRow param={param} onSubmit={onSubmit} />;
  }
  if (param.kind === "file") {
    return <FileRow param={param} onSubmit={onSubmit} />;
  }
  return <TextRow param={param} onSubmit={onSubmit} />;
}

function SelectRow({
  param,
  ctx,
  onSubmit,
}: {
  param: Extract<ParamDef, { kind: "select" }>;
  ctx: CommandContext;
  onSubmit: (value: string) => void;
}) {
  const staticOptions = "options" in param ? param.options : undefined;
  const [dynamic, setDynamic] = useState<SelectOption[] | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);

  useEffect(() => {
    if (staticOptions !== undefined) {
      setDynamic(null);
      return;
    }
    const optionsFn = "optionsFn" in param ? param.optionsFn : undefined;
    if (optionsFn === undefined) return;
    let cancelled = false;
    void (async () => {
      const loaded = await optionsFn(ctx);
      if (!cancelled) setDynamic(loaded);
    })();
    return () => {
      cancelled = true;
    };
  }, [param, ctx, staticOptions]);

  const options = useMemo<SelectOption[]>(
    () => staticOptions ?? dynamic ?? [],
    [staticOptions, dynamic],
  );

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIdx((i) =>
          options.length === 0 ? 0 : (i + 1) % options.length,
        );
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIdx((i) =>
          options.length === 0 ? 0 : (i - 1 + options.length) % options.length,
        );
      } else if (e.key === "Enter") {
        const opt = options[activeIdx];
        if (opt !== undefined) {
          e.preventDefault();
          onSubmit(opt.value);
        }
      }
    };
    window.addEventListener("keydown", handler, true);
    return () => window.removeEventListener("keydown", handler, true);
  }, [options, activeIdx, onSubmit]);

  return (
    <div>
      <div className="px-3 py-2 text-xs font-medium text-foreground">
        {param.label}
      </div>
      <div className="max-h-60 overflow-y-auto">
        {options.length === 0 ? (
          <div className="px-3 py-2 text-xs text-muted-foreground">
            Loading options…
          </div>
        ) : (
          options.map((opt, i) => (
            <button
              key={opt.value}
              type="button"
              onMouseEnter={() => setActiveIdx(i)}
              onClick={() => onSubmit(opt.value)}
              data-testid={`slash-param-option-${opt.value}`}
              className={cn(
                "flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-sm",
                i === activeIdx
                  ? "bg-accent text-accent-foreground"
                  : "text-foreground",
              )}
            >
              <span className="font-medium">{opt.label}</span>
              {opt.description !== undefined && (
                <span className="text-[11px] text-muted-foreground">
                  {opt.description}
                </span>
              )}
            </button>
          ))
        )}
      </div>
    </div>
  );
}

function TextRow({
  param,
  onSubmit,
}: {
  param: Extract<ParamDef, { kind: "text" }>;
  onSubmit: (value: string) => void;
}) {
  const [value, setValue] = useState("");
  return (
    <div className="flex flex-col gap-2 p-3">
      <label className="text-xs font-medium text-foreground">
        {param.label}
      </label>
      <input
        type="text"
        autoFocus
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            onSubmit(value);
          }
        }}
        placeholder={param.placeholder}
        data-testid={`slash-param-text-${param.name}`}
        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
      />
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={() => onSubmit(value)}
        className="self-end"
      >
        Next
      </Button>
    </div>
  );
}

function TextAreaRow({
  param,
  onSubmit,
}: {
  param: Extract<ParamDef, { kind: "textarea" }>;
  onSubmit: (value: string) => void;
}) {
  const [value, setValue] = useState("");
  return (
    <div className="flex flex-col gap-2 p-3">
      <label className="text-xs font-medium text-foreground">
        {param.label}
      </label>
      <textarea
        autoFocus
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={param.rows ?? 4}
        placeholder={param.placeholder}
        data-testid={`slash-param-textarea-${param.name}`}
        className="w-full resize-y rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
      />
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={() => onSubmit(value)}
        className="self-end"
      >
        Continue
      </Button>
    </div>
  );
}

function FileRow({
  param,
  onSubmit,
}: {
  param: Extract<ParamDef, { kind: "file" }>;
  onSubmit: (value: string) => void;
}) {
  return (
    <div className="flex flex-col gap-2 p-3">
      <label className="text-xs font-medium text-foreground">
        {param.label}
      </label>
      <input
        type="file"
        accept={param.accept}
        onChange={async (e) => {
          const file = e.target.files?.[0];
          if (file === undefined) return;
          const text = await file.text();
          onSubmit(text);
        }}
        data-testid={`slash-param-file-${param.name}`}
        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none"
      />
    </div>
  );
}
