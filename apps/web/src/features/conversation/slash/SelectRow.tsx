"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useEventListener } from "usehooks-ts";

import { cn } from "@/lib/utils/cn";

import type { CommandContext, ParamDef, SelectOption } from "./types";

type SelectParam = Extract<ParamDef, { kind: "select" }>;

interface SelectRowProps {
  param: SelectParam;
  ctx: CommandContext;
  onSubmit: (value: string) => void;
}

export function SelectRow({ param, ctx, onSubmit }: SelectRowProps) {
  const staticOptions = "options" in param ? param.options : undefined;
  const optionsFn = "optionsFn" in param ? param.optionsFn : undefined;

  const { data: dynamicOptions } = useQuery<SelectOption[]>({
    queryKey: ["slash", "select", param.name, ctx.conversationId, ctx.siteId],
    queryFn: () => {
      if (optionsFn === undefined) return Promise.resolve<SelectOption[]>([]);
      return optionsFn(ctx);
    },
    enabled: staticOptions === undefined && optionsFn !== undefined,
    staleTime: 30_000,
  });

  const options: SelectOption[] = staticOptions ?? dynamicOptions ?? [];

  const [activeIdx, setActiveIdx] = useState(0);

  useEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIdx((i) =>
        options.length === 0 ? 0 : (i + 1) % options.length,
      );
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIdx((i) =>
        options.length === 0 ? 0 : (i - 1 + options.length) % options.length,
      );
      return;
    }
    if (event.key === "Enter") {
      const opt = options[activeIdx];
      if (opt !== undefined) {
        event.preventDefault();
        onSubmit(opt.value);
      }
    }
  });

  return (
    <div>
      <div className="px-3 py-2 text-xs font-medium text-foreground">
        {param.label}
      </div>
      <div className="max-h-60 overflow-y-auto">
        {options.length === 0 ? (
          <div className="px-3 py-2 text-xs text-muted-foreground">
            Loading options...
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
