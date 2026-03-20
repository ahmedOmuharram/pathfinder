"""Vulture whitelist — functions called dynamically by kani's @ai_function decorator.

These methods are discovered and invoked via reflection at runtime.
Vulture cannot trace dynamic dispatch, so they appear "unused" statically.
"""

# ai/agents/
delegate_strategy_subtasks  # noqa
get_record_types  # noqa
list_searches  # noqa
search_for_searches  # noqa
get_search_parameters  # noqa
lookup_genes  # noqa

# ai/tools/catalog_registry.py
list_sites  # noqa
get_record_type_details  # noqa
search_example_plans  # noqa
lookup_phyletic_codes  # noqa
get_dependent_vocab  # noqa

# ai/tools/catalog_tools.py
list_transforms  # noqa
# list_sites, get_record_types, search_for_searches, list_searches,
# get_search_parameters, lookup_phyletic_codes — already listed above

# ai/tools/conversation_tools.py
save_strategy  # noqa
rename_strategy  # noqa
clear_strategy  # noqa
get_strategy_summary  # noqa

# ai/tools/execution_tools.py
get_result_count  # noqa

# ai/tools/export_tools.py
export_gene_set  # noqa

# ai/tools/research_registry.py
web_search  # noqa
literature_search  # noqa

# ai/tools/result_tools.py
get_download_url  # noqa
get_sample_records  # noqa

# ai/tools/strategy_tools/attachment_ops.py
add_step_filter  # noqa
add_step_analysis  # noqa
add_step_report  # noqa

# ai/tools/strategy_tools/discovery_ops.py
search_searches_by_keywords  # noqa
explain_operator  # noqa

# ai/tools/strategy_tools/edit_ops.py
delete_step  # noqa
undo_last_change  # noqa
rename_step  # noqa
update_step  # noqa

# ai/tools/strategy_tools/graph_ops.py
list_current_steps  # noqa
validate_graph_structure  # noqa
ensure_single_output  # noqa

# ai/tools/strategy_tools/step_ops.py
create_step  # noqa

# ai/tools/planner/artifact_tools.py
save_planning_artifact  # noqa
set_conversation_title  # noqa
report_reasoning  # noqa

# ai/tools/planner/experiment_tools.py
run_control_tests  # noqa

# ai/tools/planner/gene_tools.py
lookup_gene_records  # noqa
resolve_gene_ids_to_records  # noqa

# ai/tools/planner/optimization_tools.py
optimize_search_parameters  # noqa

# ai/tools/planner/workbench_tools.py
create_workbench_gene_set  # noqa
run_gene_set_enrichment  # noqa
list_workbench_gene_sets  # noqa

# ai/tools/workbench_read_tools.py
get_evaluation_summary  # noqa
get_enrichment_results  # noqa
get_confidence_scores  # noqa
get_step_contributions  # noqa
get_experiment_config  # noqa
get_ensemble_analysis  # noqa
get_result_gene_lists  # noqa

# services/experiment/ai_refinement_tools.py
refine_with_search  # noqa
refine_with_gene_ids  # noqa
re_evaluate_controls  # noqa

# services/experiment/ai_analysis_tools.py
fetch_result_records  # noqa
lookup_gene_detail  # noqa
get_attribute_distribution  # noqa
compare_gene_groups  # noqa
search_results  # noqa
