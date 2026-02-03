import type { StrategyStep } from "@/types/strategy";
import { inferStepKind } from "@/core/strategyGraph";

export function getZeroResultSuggestions(step: StrategyStep): string[] {
  const suggestions: string[] = [];

  // Broad, always-relevant suggestions
  suggestions.push("Relax overly strict parameters/filters (broader thresholds, stages, datasets).");
  suggestions.push("Verify organism / life stage / strain matches the dataset/search you picked.");

  const kind = inferStepKind(step);
  if (kind === "combine") {
    const op = step.operator;
    if (op === "INTERSECT") {
      suggestions.push("If you expected results from either branch, change INTERSECT (AND) to UNION (OR).");
    } else if (op === "MINUS_LEFT" || op === "MINUS_RIGHT") {
      suggestions.push("If you expected to remove the other branch, verify MINUS direction (swap MINUS_LEFT vs MINUS_RIGHT).");
    } else if (op === "COLOCATE") {
      suggestions.push("For COLOCATE/NEAR, increase upstream/downstream distance and verify feature types.");
    }
    suggestions.push("Check that both input steps are non-zero before combining.");
  } else if (kind === "transform") {
    suggestions.push("If the input step is zero, fix upstream; otherwise adjust transform parameters.");
    suggestions.push("For cross-species mapping, consider an orthology transform (find orthologs) before/after this step.");
  } else if (kind === "search") {
    suggestions.push("Try an alternative search with similar meaning (broader keyword / different dataset).");
  }

  // Keep it short; UI should not overwhelm.
  return suggestions.slice(0, 5);
}

