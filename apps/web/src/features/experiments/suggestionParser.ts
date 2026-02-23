/**
 * Parses AI markdown responses to extract structured fenced code blocks
 * and split the response into renderable segments.
 */

export interface SearchSuggestion {
  searchName: string;
  recordType: string;
  displayName: string;
  description: string;
  rationale: string;
  suggestedParameters?: Record<string, string>;
}

export interface ControlGeneSuggestion {
  geneId: string;
  geneName: string;
  product: string;
  organism: string;
  role: "positive" | "negative";
  rationale: string;
}

export interface ParamSuggestion {
  parameters: Record<string, string>;
  rationale: string;
}

export interface RunConfigSuggestion {
  name?: string;
  enableCrossValidation?: boolean;
  kFolds?: number;
  enrichmentTypes?: string[];
  rationale: string;
}

type BlockTag = "suggestion" | "control_gene" | "param_suggestion" | "run_config";

export type SuggestionSegment =
  | { type: "text"; content: string }
  | { type: "suggestion"; data: SearchSuggestion }
  | { type: "control_gene"; data: ControlGeneSuggestion }
  | { type: "param_suggestion"; data: ParamSuggestion }
  | { type: "run_config"; data: RunConfigSuggestion };

const BLOCK_RE =
  /```(suggestion|control_gene|param_suggestion|run_config)\s*\n([\s\S]*?)```/g;

function tryParseSearchSuggestion(raw: string): SearchSuggestion | null {
  try {
    const obj = JSON.parse(raw);
    if (
      typeof obj.searchName === "string" &&
      typeof obj.recordType === "string" &&
      typeof obj.displayName === "string"
    ) {
      return {
        searchName: obj.searchName,
        recordType: obj.recordType,
        displayName: obj.displayName,
        description: obj.description ?? "",
        rationale: obj.rationale ?? "",
        suggestedParameters: obj.suggestedParameters ?? undefined,
      };
    }
  } catch {
    /* malformed JSON */
  }
  return null;
}

function tryParseControlGene(raw: string): ControlGeneSuggestion | null {
  try {
    const obj = JSON.parse(raw);
    if (typeof obj.geneId === "string" && typeof obj.role === "string") {
      const role = obj.role === "negative" ? "negative" : "positive";
      return {
        geneId: obj.geneId,
        geneName: obj.geneName ?? "",
        product: obj.product ?? "",
        organism: obj.organism ?? "",
        role,
        rationale: obj.rationale ?? "",
      };
    }
  } catch {
    /* malformed JSON */
  }
  return null;
}

function tryParseParamSuggestion(raw: string): ParamSuggestion | null {
  try {
    const obj = JSON.parse(raw);
    if (typeof obj.parameters === "object" && obj.parameters !== null) {
      const params: Record<string, string> = {};
      for (const [k, v] of Object.entries(obj.parameters)) {
        params[k] = String(v);
      }
      return {
        parameters: params,
        rationale: typeof obj.rationale === "string" ? obj.rationale : "",
      };
    }
  } catch {
    /* malformed JSON */
  }
  return null;
}

function tryParseRunConfig(raw: string): RunConfigSuggestion | null {
  try {
    const obj = JSON.parse(raw);
    if (typeof obj === "object" && obj !== null) {
      return {
        name: typeof obj.name === "string" ? obj.name : undefined,
        enableCrossValidation:
          typeof obj.enableCrossValidation === "boolean"
            ? obj.enableCrossValidation
            : undefined,
        kFolds: typeof obj.kFolds === "number" ? obj.kFolds : undefined,
        enrichmentTypes: Array.isArray(obj.enrichmentTypes)
          ? obj.enrichmentTypes.filter((t: unknown) => typeof t === "string")
          : undefined,
        rationale: typeof obj.rationale === "string" ? obj.rationale : "",
      };
    }
  } catch {
    /* malformed JSON */
  }
  return null;
}

const PARSERS: Record<BlockTag, (body: string) => SuggestionSegment | null> = {
  suggestion: (body) => {
    const data = tryParseSearchSuggestion(body);
    return data ? { type: "suggestion", data } : null;
  },
  control_gene: (body) => {
    const data = tryParseControlGene(body);
    return data ? { type: "control_gene", data } : null;
  },
  param_suggestion: (body) => {
    const data = tryParseParamSuggestion(body);
    return data ? { type: "param_suggestion", data } : null;
  },
  run_config: (body) => {
    const data = tryParseRunConfig(body);
    return data ? { type: "run_config", data } : null;
  },
};

/**
 * Split an AI response into text segments and typed structured cards.
 */
export function parseSuggestions(markdown: string): SuggestionSegment[] {
  const segments: SuggestionSegment[] = [];
  let lastIndex = 0;

  for (const match of markdown.matchAll(BLOCK_RE)) {
    const start = match.index!;
    if (start > lastIndex) {
      segments.push({ type: "text", content: markdown.slice(lastIndex, start) });
    }

    const tag = match[1] as BlockTag;
    const body = match[2].trim();
    const segment = PARSERS[tag](body);

    if (segment) {
      segments.push(segment);
    } else {
      segments.push({ type: "text", content: match[0] });
    }

    lastIndex = start + match[0].length;
  }

  if (lastIndex < markdown.length) {
    segments.push({ type: "text", content: markdown.slice(lastIndex) });
  }

  return segments;
}
