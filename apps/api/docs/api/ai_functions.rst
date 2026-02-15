AI Functions Reference
======================

Complete list of tools (``@ai_function()``) exposed to the LLM, grouped by
mode and purpose. The LLM sees these as callable functions with schemas.

Execute Mode (PathfinderAgent)
------------------------------

**Catalog / Discovery**

- ``list_sites`` — List VEuPathDB sites (RAG + WDK)
- ``get_record_types`` — Record types for the site
- ``get_record_type_details`` — Details for one record type (RAG)
- ``list_searches`` — Searches for a record type
- ``search_for_searches`` — Semantic search for searches
- ``get_search_parameters`` — Parameter specs for a search
- ``get_dependent_vocab`` — Refresh dependent parameter options
- ``search_example_plans`` — Search example strategies (RAG + WDK)

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

**Execution / Outputs**

- ``build_strategy`` — Build or update WDK strategy
- ``preview_results`` — Preview step results
- ``get_result_count`` — Get result count for a step
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

Plan Mode (PathfinderPlannerAgent)
----------------------------------

**Catalog (live only in plan mode)**

- ``list_sites``
- ``get_record_types``
- ``list_searches``
- ``search_for_searches``
- ``get_search_parameters``

**Planning Artifacts**

- ``save_planning_artifact`` — Save artifact (title, summary, parameters, proposed_strategy_plan)
- ``save_delegation_plan_draft`` — Save/update delegation draft
- ``request_executor_build`` — Hand off to executor with goal and optional plan
- ``list_saved_planning_artifacts`` — List saved artifacts
- ``get_saved_planning_artifact`` — Get one artifact by ID

**Validation & Research**

- ``run_control_tests`` — Run positive/negative control gene lists
- ``optimize_search_parameters`` — Optimize parameters (Bayesian, grid, random)
- ``lookup_gene_records`` — Look up genes by text
- ``resolve_gene_ids_to_records`` — Resolve gene IDs to records

**Research**

- ``web_search``
- ``literature_search``

**Session**

- ``set_conversation_title`` — Set plan session title
- ``report_reasoning`` — Report reasoning to the user

SubtaskAgent (Sub-kani)
------------------------

Same tools as PathfinderAgent **except** ``delegate_strategy_subtasks``.
Each sub-kani has catalog, graph-building, execution, and research tools,
but cannot delegate further.

Detailed Tool Docs
------------------

See :doc:`tools` for full module reference (registry, planner_registry,
research_registry, execution_tools).
