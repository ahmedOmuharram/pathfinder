import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { X, Loader2, AlertCircle, Upload, Info } from "lucide-react";
import { resolveGeneIds, type ResolvedGene } from "@/lib/api/client";

interface ValidatedGeneInputProps {
  siteId: string;
  genes: ResolvedGene[];
  onGenesChange: (genes: ResolvedGene[]) => void;
  /** Gene IDs already assigned to the opposite control list. */
  excludeGeneIds?: Set<string>;
  label: string;
  placeholder?: string;
  variant?: "positive" | "negative";
}

export function ValidatedGeneInput({
  siteId,
  genes,
  onGenesChange,
  excludeGeneIds,
  label,
  placeholder = "Type a gene ID and press Enter…",
  variant = "positive",
}: ValidatedGeneInputProps) {
  const [inputValue, setInputValue] = useState("");
  const [validating, setValidating] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [hoveredGene, setHoveredGene] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const chipContainerRef = useRef<HTMLDivElement>(null);

  const isPositive = variant === "positive";

  const validateAndAdd = useCallback(
    async (raw: string) => {
      const ids = raw
        .split(/[\n,\s]+/)
        .map((s) => s.trim())
        .filter(Boolean);

      if (ids.length === 0) return;

      const existing = new Set(genes.map((g) => g.geneId));
      const newIds = ids.filter((id) => !existing.has(id) && !excludeGeneIds?.has(id));
      if (newIds.length === 0) {
        setInputValue("");
        return;
      }

      setValidating(true);
      setErrors([]);

      try {
        const resp = await resolveGeneIds(siteId, newIds);
        const nextGenes = [...genes, ...resp.resolved];
        onGenesChange(nextGenes);

        if (resp.unresolved.length > 0) {
          setErrors(resp.unresolved);
        }
      } catch {
        setErrors(newIds);
      } finally {
        setValidating(false);
        setInputValue("");
      }
    },
    [siteId, genes, onGenesChange, excludeGeneIds],
  );

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === "Tab" || e.key === ",") {
      e.preventDefault();
      if (inputValue.trim()) {
        validateAndAdd(inputValue);
      }
    }
    if (e.key === "Backspace" && inputValue === "" && genes.length > 0) {
      onGenesChange(genes.slice(0, -1));
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const text = e.clipboardData.getData("text");
    if (text.includes(",") || text.includes("\n") || text.includes("\t")) {
      e.preventDefault();
      validateAndAdd(text);
    }
  };

  const removeGene = (geneId: string) => {
    onGenesChange(genes.filter((g) => g.geneId !== geneId));
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        validateAndAdd(reader.result);
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  const handleHoverEnter = (geneId: string) => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    hoverTimeoutRef.current = setTimeout(() => setHoveredGene(geneId), 200);
  };

  const handleHoverLeave = () => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    hoverTimeoutRef.current = setTimeout(() => setHoveredGene(null), 150);
  };

  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    };
  }, []);

  const chipBorder = isPositive ? "border-emerald-200" : "border-red-200";
  const chipBg = isPositive ? "bg-emerald-50" : "bg-red-50";
  const chipText = isPositive ? "text-emerald-800" : "text-red-800";
  const chipHoverBg = isPositive ? "hover:bg-emerald-100" : "hover:bg-red-100";

  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          {label}
        </label>
        <label className="flex cursor-pointer items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500 transition hover:bg-slate-200">
          <Upload className="h-3 w-3" />
          Upload CSV
          <input
            type="file"
            accept=".csv,.txt"
            className="hidden"
            onChange={handleFileUpload}
          />
        </label>
      </div>

      <div
        ref={chipContainerRef}
        className="flex min-h-[72px] flex-wrap items-start gap-1.5 rounded-md border border-slate-200 px-2.5 py-2 focus-within:border-slate-300"
        onClick={() => inputRef.current?.focus()}
      >
        {genes.map((gene) => (
          <GeneChip
            key={gene.geneId}
            gene={gene}
            chipBorder={chipBorder}
            chipBg={chipBg}
            chipText={chipText}
            chipHoverBg={chipHoverBg}
            isHovered={hoveredGene === gene.geneId}
            onHoverEnter={() => handleHoverEnter(gene.geneId)}
            onHoverLeave={handleHoverLeave}
            onRemove={() => removeGene(gene.geneId)}
          />
        ))}

        {validating && (
          <span className="flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-500">
            <Loader2 className="h-3 w-3 animate-spin" />
            Validating…
          </span>
        )}

        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          onBlur={() => {
            if (inputValue.trim()) validateAndAdd(inputValue);
          }}
          placeholder={genes.length === 0 ? placeholder : ""}
          className="min-w-[120px] flex-1 border-none bg-transparent py-0.5 font-mono text-[12px] outline-none placeholder:text-slate-400"
          disabled={validating}
        />
      </div>

      {errors.length > 0 && (
        <div className="mt-1.5 flex items-start gap-1.5 rounded border border-amber-200 bg-amber-50 px-2.5 py-1.5">
          <AlertCircle className="mt-0.5 h-3 w-3 shrink-0 text-amber-500" />
          <div className="text-[10px] text-amber-800">
            <span className="font-medium">
              {errors.length === 1 ? "ID" : `${errors.length} IDs`} not recognized:
            </span>{" "}
            <span className="font-mono">{errors.join(", ")}</span>
            <span className="ml-1 text-amber-600">
              — only exact gene IDs from the database are accepted.
            </span>
          </div>
          <button
            type="button"
            onClick={() => setErrors([])}
            className="ml-auto shrink-0 rounded p-0.5 text-amber-400 hover:bg-amber-100 hover:text-amber-600"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      )}

      <div className="mt-1 flex items-center justify-between">
        <span className="text-[10px] text-slate-400">
          {genes.length} validated gene{genes.length !== 1 ? "s" : ""}
        </span>
        {genes.length === 0 && !validating && errors.length === 0 && (
          <span className="flex items-center gap-1 text-[10px] text-slate-400">
            <Info className="h-3 w-3" />
            Enter exact IDs (e.g. PF3D7_1133400) — each is verified against the
            database. Use the search panel above to find IDs.
          </span>
        )}
      </div>
    </div>
  );
}

function GeneChip({
  gene,
  chipBorder,
  chipBg,
  chipText,
  chipHoverBg,
  isHovered,
  onHoverEnter,
  onHoverLeave,
  onRemove,
}: {
  gene: ResolvedGene;
  chipBorder: string;
  chipBg: string;
  chipText: string;
  chipHoverBg: string;
  isHovered: boolean;
  onHoverEnter: () => void;
  onHoverLeave: () => void;
  onRemove: () => void;
}) {
  return (
    <span
      className={`group relative inline-flex items-center gap-1 rounded-full border ${chipBorder} ${chipBg} py-0.5 pl-2 pr-1 font-mono text-[11px] ${chipText}`}
      onMouseEnter={onHoverEnter}
      onMouseLeave={onHoverLeave}
    >
      {gene.geneId}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        className={`rounded-full p-0.5 opacity-60 transition ${chipHoverBg} hover:opacity-100`}
      >
        <X className="h-2.5 w-2.5" />
      </button>

      {isHovered && <GenePopover gene={gene} />}
    </span>
  );
}

function GenePopover({ gene }: { gene: ResolvedGene }) {
  return (
    <div
      className="absolute left-0 top-full z-50 mt-1.5 w-72 rounded-lg border border-slate-200 bg-white p-3 shadow-lg"
      onMouseEnter={() => {}}
      onMouseLeave={() => {}}
    >
      <div className="mb-1.5 flex items-center gap-2">
        <span className="font-mono text-[12px] font-semibold text-slate-900">
          {gene.geneId}
        </span>
        {gene.geneName && (
          <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-700">
            {gene.geneName}
          </span>
        )}
      </div>

      <dl className="space-y-1 text-[10px]">
        {gene.product && (
          <div>
            <dt className="font-medium text-slate-500">Product</dt>
            <dd className="text-slate-700">{gene.product}</dd>
          </div>
        )}
        {gene.organism && (
          <div>
            <dt className="font-medium text-slate-500">Organism</dt>
            <dd className="italic text-slate-700">{gene.organism}</dd>
          </div>
        )}
        {gene.geneType && (
          <div>
            <dt className="font-medium text-slate-500">Type</dt>
            <dd className="text-slate-700">{gene.geneType}</dd>
          </div>
        )}
        {gene.location && (
          <div>
            <dt className="font-medium text-slate-500">Location</dt>
            <dd className="font-mono text-slate-700">{gene.location}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}
