const TOOL_LABELS: Record<string, string> = {
  // Lead dispatch / inspection
  read_ledger_section: "Read ledger",
  classify_user_intent: "Classify intent",
  consult_user: "Ask the user",
  recover_failed_steps: "Recover steps",
  // FRAME
  frame_problem: "Frame problem",
  search_for_searches: "Search catalog",
  get_search_overview: "Inspect search",
  set_criterion: "Set criterion",
  set_structure: "Set structure",
  drop_criterion: "Drop criterion",
  // Experiments / controls
  compare_search_variants: "Compare variants",
  compare_variants_scored: "Score variants",
  build_control_set: "Build control set",
  list_control_sets: "List control sets",
  import_control_ids_from_gene_set: "Controls from gene set",
  import_control_ids_from_strategy: "Controls from strategy",
  // BUILD / strategy
  build_strategy: "Build strategy",
  verify_strategy: "Verify strategy",
  update_leaf_params: "Update parameters",
  replace_subtree: "Replace subtree",
  // Verification / durable
  run_control_tests_on_step: "Run control tests",
  optimize_search_parameters: "Optimize parameters",
  run_gene_set_enrichment: "Gene-set enrichment",
  // The name the enrichment task itself puts on the wire.
  geneset_enrichment: "Gene set enrichment",
  // Scratchpad / memory
  note: "Save note",
  update_note: "Update note",
  delete_note: "Delete note",
  pin_note: "Pin note",
  search_notes: "Search notes",
  list_notes: "List notes",
  promote_to_memory: "Save to memory",
  search_memory: "Search memory",
  remember: "Remember",
  // Research
  web_search: "Web search",
  literature_search: "Literature search",
};

/**
 * Render-ready label for a tool name shown anywhere in the UI (Lead tool
 * cards, sub-agent steps, task cards, approval prompts). Falls back to a
 * Title-cased version of the snake_case name for unmapped tools.
 */
export function humanizeToolName(name: string): string {
  const known = TOOL_LABELS[name];
  if (known !== undefined) return known;
  const spaced = name.replace(/^tool-/, "").replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
