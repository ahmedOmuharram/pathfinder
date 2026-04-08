"""Verification-phase toolset — 18 tools for testing, analyzing, and exporting results."""

from pydantic_ai.toolsets.function import FunctionToolset

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.standalone.execution import get_estimated_size
from pathfinder.ai.tools.standalone.experiment import (
    run_control_tests_on_search,
    run_control_tests_on_step,
)
from pathfinder.ai.tools.standalone.export import export_gene_set
from pathfinder.ai.tools.standalone.optimization import optimize_search_parameters
from pathfinder.ai.tools.standalone.results import (
    get_download_url,
    get_sample_records,
)
from pathfinder.ai.tools.standalone.strategy_graph import get_strategy
from pathfinder.ai.tools.standalone.think import think
from pathfinder.ai.tools.standalone.workbench import (
    create_workbench_gene_set,
    list_workbench_gene_sets,
    run_gene_set_enrichment,
)
from pathfinder.ai.tools.standalone.workbench_read import (
    get_confidence_scores,
    get_enrichment_results,
    get_ensemble_analysis,
    get_evaluation_summary,
    get_experiment_config,
    get_result_gene_lists,
    get_step_contributions,
)


def build_toolset() -> FunctionToolset[AgentDeps]:
    """Build the verification-phase toolset."""
    return FunctionToolset(
        tools=[
            get_estimated_size,
            get_sample_records,
            get_download_url,
            run_control_tests_on_step,
            run_control_tests_on_search,
            optimize_search_parameters,
            create_workbench_gene_set,
            run_gene_set_enrichment,
            list_workbench_gene_sets,
            export_gene_set,
            get_evaluation_summary,
            get_enrichment_results,
            get_confidence_scores,
            get_step_contributions,
            get_experiment_config,
            get_ensemble_analysis,
            get_result_gene_lists,
            get_strategy,
            think,
        ],
    )
