"use client";

import type { ColocationParams } from "@pathfinder/shared";
import { Card } from "@/lib/components/ui/Card";
import { Input } from "@/lib/components/ui/Input";

// ── Default colocation params (WDK defaults) ────────────────────────────

export const DEFAULT_COLOCATION: ColocationParams = {
  operation: "overlaps",
  strand: "either strand",
  output: "a",
  regionA: "exact",
  beginA: "start",
  beginDirectionA: "+",
  beginOffsetA: 0,
  endA: "stop",
  endDirectionA: "+",
  endOffsetA: 0,
  regionB: "exact",
  beginB: "start",
  beginDirectionB: "+",
  beginOffsetB: 0,
  endB: "stop",
  endDirectionB: "+",
  endOffsetB: 0,
};

export function resolveParams(params: ColocationParams | null | undefined): ColocationParams {
  return { ...DEFAULT_COLOCATION, ...params };
}

// ── Toggle button group ─────────────────────────────────────────────────

type ToggleOption<T extends string> = { value: T; label: string };

function ToggleGroup<T extends string>({
  options,
  value,
  onChange,
  columns,
}: {
  options: ToggleOption<T>[];
  value: T;
  onChange: (next: T) => void;
  columns?: number;
}) {
  const gridCols =
    columns === 2
      ? "grid-cols-2"
      : columns === 4
        ? "grid-cols-4"
        : "grid-cols-3";
  return (
    <div className={`grid ${gridCols} gap-1`}>
      {options.map((opt) => {
        const selected = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`rounded-md border px-2 py-1.5 text-xs font-semibold transition-colors duration-150 ${
              selected
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-card text-foreground hover:border-input"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

// ── Offset row (anchor + direction + offset number) ─────────────────────

function OffsetRow({
  label,
  anchor,
  direction,
  offset,
  onAnchorChange,
  onDirectionChange,
  onOffsetChange,
}: {
  label: string;
  anchor: "start" | "stop";
  direction: "+" | "-";
  offset: number;
  onAnchorChange: (v: "start" | "stop") => void;
  onDirectionChange: (v: "+" | "-") => void;
  onOffsetChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="flex items-center gap-1">
        <ToggleGroup
          options={[
            { value: "start" as const, label: "Start" },
            { value: "stop" as const, label: "Stop" },
          ]}
          value={anchor}
          onChange={onAnchorChange}
          columns={2}
        />
        <ToggleGroup
          options={[
            { value: "+" as const, label: "+" },
            { value: "-" as const, label: "\u2212" },
          ]}
          value={direction}
          onChange={onDirectionChange}
          columns={2}
        />
        <Input
          type="number"
          min={0}
          value={offset}
          onChange={(e) => onOffsetChange(Math.max(0, Number(e.target.value || 0)))}
          className="h-7 w-20 bg-card text-xs"
        />
      </div>
    </div>
  );
}

// ── Region editor (region type + begin/end offset rows) ─────────────────

type RegionSuffix = "A" | "B";

function RegionEditor({
  label,
  params,
  suffix,
  onChange,
}: {
  label: string;
  params: ColocationParams;
  suffix: RegionSuffix;
  onChange: (patch: Partial<ColocationParams>) => void;
}) {
  const regionKey = `region${suffix}` as const;
  const beginKey = `begin${suffix}` as const;
  const beginDirKey = `beginDirection${suffix}` as const;
  const beginOffKey = `beginOffset${suffix}` as const;
  const endKey = `end${suffix}` as const;
  const endDirKey = `endDirection${suffix}` as const;
  const endOffKey = `endOffset${suffix}` as const;

  const region = params[regionKey] ?? "exact";
  const showDetails = region !== "exact";

  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <ToggleGroup
        options={[
          { value: "exact" as const, label: "Exact" },
          { value: "upstream" as const, label: "Upstream" },
          { value: "downstream" as const, label: "Downstream" },
          { value: "custom" as const, label: "Custom" },
        ]}
        value={region}
        onChange={(r) => {
          const patch: Partial<ColocationParams> = { [regionKey]: r };
          if (r === "exact") {
            patch[beginKey] = "start";
            patch[beginDirKey] = "+";
            patch[beginOffKey] = 0;
            patch[endKey] = "stop";
            patch[endDirKey] = "+";
            patch[endOffKey] = 0;
          } else if (r === "upstream") {
            patch[beginKey] = "start";
            patch[beginDirKey] = "-";
            patch[beginOffKey] = 0;
            patch[endKey] = "start";
            patch[endDirKey] = "+";
            patch[endOffKey] = 0;
          } else if (r === "downstream") {
            patch[beginKey] = "stop";
            patch[beginDirKey] = "-";
            patch[beginOffKey] = 0;
            patch[endKey] = "stop";
            patch[endDirKey] = "+";
            patch[endOffKey] = 0;
          }
          onChange(patch);
        }}
        columns={4}
      />
      {showDetails && (
        <div className="grid grid-cols-2 gap-3 rounded-md border border-border bg-background p-2">
          <OffsetRow
            label="Begin"
            anchor={params[beginKey] ?? "start"}
            direction={params[beginDirKey] ?? "+"}
            offset={params[beginOffKey] ?? 0}
            onAnchorChange={(v) => onChange({ [beginKey]: v })}
            onDirectionChange={(v) => onChange({ [beginDirKey]: v })}
            onOffsetChange={(v) => onChange({ [beginOffKey]: v })}
          />
          <OffsetRow
            label="End"
            anchor={params[endKey] ?? "stop"}
            direction={params[endDirKey] ?? "+"}
            offset={params[endOffKey] ?? 0}
            onAnchorChange={(v) => onChange({ [endKey]: v })}
            onDirectionChange={(v) => onChange({ [endDirKey]: v })}
            onOffsetChange={(v) => onChange({ [endOffKey]: v })}
          />
        </div>
      )}
    </div>
  );
}

// ── Main colocation editor ──────────────────────────────────────────────

export function ColocationEditor({
  params,
  onPatch,
}: {
  params: ColocationParams;
  onPatch: (patch: Partial<ColocationParams>) => void;
}) {
  return (
    <Card className="mt-3 space-y-3 rounded-md p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Colocation parameters
      </div>

      {/* Operation */}
      <div className="space-y-1">
        <div className="text-xs text-muted-foreground">Operation</div>
        <ToggleGroup
          options={[
            { value: "overlaps" as const, label: "Overlaps" },
            { value: "contains" as const, label: "Contains" },
            { value: "is contained in" as const, label: "Is contained in" },
          ]}
          value={params.operation ?? "overlaps"}
          onChange={(v) => onPatch({ operation: v })}
        />
      </div>

      {/* Strand */}
      <div className="space-y-1">
        <div className="text-xs text-muted-foreground">Strand</div>
        <ToggleGroup
          options={[
            { value: "either strand" as const, label: "Either" },
            { value: "same strand" as const, label: "Same" },
            { value: "opposite strand" as const, label: "Opposite" },
          ]}
          value={params.strand ?? "either strand"}
          onChange={(v) => onPatch({ strand: v })}
        />
      </div>

      {/* Output */}
      <div className="space-y-1">
        <div className="text-xs text-muted-foreground">Output</div>
        <ToggleGroup
          options={[
            { value: "a" as const, label: "Step A" },
            { value: "b" as const, label: "Step B" },
          ]}
          value={params.output ?? "a"}
          onChange={(v) => onPatch({ output: v })}
          columns={2}
        />
      </div>

      {/* Region A */}
      <RegionEditor
        label="Region A"
        params={params}
        suffix="A"
        onChange={onPatch}
      />

      {/* Region B */}
      <RegionEditor
        label="Region B"
        params={params}
        suffix="B"
        onChange={onPatch}
      />
    </Card>
  );
}
