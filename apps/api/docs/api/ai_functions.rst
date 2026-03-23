AI Functions Reference
======================

Complete list of tools (``@ai_function()``) exposed to the LLM. The unified
agent has access to all tools and decides per-turn which to use.

PathfinderAgent (Unified)
-------------------------

**Catalog / Discovery**

- ``list_sites`` — List VEuPathDB sites
- ``get_record_types`` — Record types for the site
- ``list_searches`` — Searches for a record type
- ``search_for_searches`` — Semantic search for searches
- ``get_search_parameters`` — Parameter specs for a search
- ``get_dependent_vocab`` — Refresh dependent parameter options
- ``lookup_phyletic_codes`` — Look up phyletic pattern codes for organisms
- ``search_example_plans`` — Search example strategies

**Graph Building / Editing**

- ``create_step`` — Create a search, transform, or combine step
- ``list_current_steps`` — List steps with WDK IDs and counts
- ``validate_graph_structure`` — Validate structure and single-output
- ``ensure_single_output`` — Combine loose roots into one output
- ``delete_step`` — Delete a step
- ``undo_last_change`` — Undo last graph mutation
- ``rename_step`` — Rename a step
- ``update_step`` — Update step parameters
- ``add_step_filter`` — Add filter to a step
- ``add_step_analysis`` — Add analysis to a step
- ``add_step_report`` — Add report to a step
- ``explain_operator`` — Explain combine operator (UNION, etc.)
- ``search_searches_by_keywords`` — Keyword search for available searches

**Execution / Outputs**

- ``get_result_count`` — Get result count for a built step
- ``get_download_url`` — Get download URL for results
- ``get_sample_records`` — Get sample records from a step

**Strategy Metadata**

- ``save_strategy`` — Save strategy to WDK
- ``rename_strategy`` — Rename the strategy
- ``clear_strategy`` — Clear the graph
- ``get_strategy_summary`` — Summary of current strategy

**Delegation**

- ``delegate_strategy_subtasks`` — Spawn sub-kanis for multi-step build

**Research**

- ``web_search`` — DuckDuckGo web search
- ``literature_search`` — Scientific literature search

**Validation & Optimization**

- ``run_control_tests`` — Run positive/negative control gene lists
- ``optimize_search_parameters`` — Optimize parameters (Bayesian, grid, random)
- ``lookup_gene_records`` — Look up genes by text
- ``resolve_gene_ids_to_records`` — Resolve gene IDs to records

**Artifacts**

- ``save_planning_artifact`` — Save artifact (title, summary, parameters, proposed_strategy_plan)

**Workbench / Gene Sets**

- ``create_workbench_gene_set`` — Create a gene set in the workbench
- ``run_gene_set_enrichment`` — Run enrichment analysis on a gene set
- ``list_workbench_gene_sets`` — List available gene sets

**Export**

- ``export_gene_set`` — Export a gene set as CSV or TXT

**Session**

- ``set_conversation_title`` — Set conversation title
- ``report_reasoning`` — Report reasoning to the user

SubtaskAgent (Sub-kani)
------------------------

Has **catalog**, **graph building / editing**, **execution / outputs**,
**strategy metadata**, and **research** tools -- the same core tools as
PathfinderAgent. Does **not** have delegation, validation & optimization,
workbench, export, or artifact tools.

Detailed Tool Docs
------------------

See :doc:`tools` for full module reference (unified_registry, registry,
research_registry, execution_tools).
