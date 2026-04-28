"""Validate-specialist toolset.

Read-heavy inspection plus the two control-test tools (one of which is
durable) plus the cross-cutting trio (think / search_memory / remember)
plus the specialist-only ``exit_specialist`` exit tool.

Strategy mutation tools are deliberately excluded — validate inspects
and tests, never edits.
"""

from pydantic_ai.tools import Tool
from pydantic_ai.toolsets.abstract import AbstractToolset
from pydantic_ai.toolsets.function import FunctionToolset

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone.execution import get_estimated_size
from pathfinder.ai.tools.standalone.exit_specialist import exit_specialist
from pathfinder.ai.tools.standalone.experiment import (
    run_control_tests_on_search,
    run_control_tests_on_step,
)
from pathfinder.ai.tools.standalone.memory_tools import remember, search_memory
from pathfinder.ai.tools.standalone.results import get_sample_records
from pathfinder.ai.tools.standalone.strategy_graph import get_strategy
from pathfinder.ai.tools.standalone.think import think
from pathfinder.ai.tools.standalone.workbench_read import (
    get_confidence_scores,
    get_ensemble_analysis,
    get_evaluation_summary,
    get_experiment_config,
    get_result_gene_lists,
    get_step_contributions,
)


def build_validate_toolset() -> AbstractToolset[AgentDeps]:
    return FunctionToolset(
        tools=[
            # Read-only inspection
            get_estimated_size,
            get_sample_records,
            get_strategy,
            get_evaluation_summary,
            get_confidence_scores,
            get_step_contributions,
            get_experiment_config,
            get_ensemble_analysis,
            get_result_gene_lists,
            # Validation (one is durable, sequential matters per existing
            # convention — see ``toolsets/verification.py`` for rationale)
            Tool(run_control_tests_on_step, sequential=True),
            run_control_tests_on_search,
            # Cross-cutting
            think,
            search_memory,
            remember,
            # Specialist-only exit
            exit_specialist,
        ],
    )
