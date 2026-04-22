"""Verification-phase toolset for testing, analyzing, and exporting results."""

from pydantic_ai.tools import Tool
from pydantic_ai.toolsets.function import FunctionToolset

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone.execution import get_estimated_size
from pathfinder.ai.tools.standalone.experiment import (
    run_control_tests_on_search,
    run_control_tests_on_step,
)
from pathfinder.ai.tools.standalone.export import export_gene_set
from pathfinder.ai.tools.standalone.memory_tools import remember, search_memory
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
    """Build the verification-phase toolset.

    Phase exit is handled by ``output_type=VerificationDecision`` on the
    verification agent — no ``finish_*`` tool is exposed.

    Every ``@durable_tool`` is also registered with ``sequential=True``.
    Durable tools suspend the graph via ``interrupt()`` on invocation; if
    pydantic-ai were to run a durable peer in parallel with a sibling tool,
    the sibling's ``ToolReturnPart`` would be orphaned when the interrupt
    escapes ``_call_tools`` and cancels peers. Sequential execution on the
    whole batch guarantees paired ``tool_call_id`` / ``tool_return_id`` in
    every persisted message history.

    ``optimize_search_parameters`` also carries ``requires_approval=True``
    because it runs up to ``settings.budget`` trials (default 30).
    """
    return FunctionToolset(
        tools=[
            get_estimated_size,
            get_sample_records,
            get_download_url,
            Tool(run_control_tests_on_step, sequential=True),
            run_control_tests_on_search,
            Tool(
                optimize_search_parameters,
                requires_approval=True,
                sequential=True,
            ),
            create_workbench_gene_set,
            Tool(run_gene_set_enrichment, sequential=True),
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
            search_memory,
            remember,
        ],
    )
