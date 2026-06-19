"""Verification-phase toolset for testing, analyzing, and exporting results."""

from pydantic_ai.tools import RunContext, Tool
from pydantic_ai.toolsets.abstract import AbstractToolset
from pydantic_ai.toolsets.function import FunctionToolset

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone.escape_hatch import (
    request_search_inspection,
)
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
from pathfinder.ai.tools.toolsets._dynamic import (
    DynamicEnumToolset,
    EnumOverrides,
    live_wdk_step_ids,
)


def _verification_enum_overrides(
    ctx: RunContext[AgentDeps],
) -> EnumOverrides:
    """Constrain ``wdk_step_id`` args to steps actually built in WDK and
    ``target_search_name`` to discovery's selected universe.

    Verification tools take ``wdk_step_id: int`` (the WDK-side numeric
    id assigned after a step is pushed) — only steps that have been
    built can be queried, so the enum is restricted to ids visible in
    ``strategy_session.sync_state.wdk_step_ids``.
    """
    overrides: EnumOverrides = {}
    wdk_ids = live_wdk_step_ids(ctx.deps)
    if wdk_ids:
        for tool in (
            "get_estimated_size",
            "get_sample_records",
            "get_download_url",
            "run_control_tests_on_step",
        ):
            overrides[(tool, "wdk_step_id")] = list(wdk_ids)
    selected = sorted(ctx.deps.agent_state.selected_search_names())
    if selected:
        overrides[("run_control_tests_on_search", "target_search_name")] = selected
    return overrides


def build_toolset() -> AbstractToolset[AgentDeps]:
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

    ``optimize_search_parameters`` carries ``requires_approval=True``: the SDK
    emits a ``ToolApprovalRequestChunk`` so the user confirms before a
    ~15-minute parameter sweep launches on the worker.
    """
    base: FunctionToolset[AgentDeps] = FunctionToolset(
        max_retries=3,
        tools=[
            get_estimated_size,
            get_sample_records,
            get_download_url,
            Tool(run_control_tests_on_step, sequential=True, max_retries=3),
            Tool(
                optimize_search_parameters,
                sequential=True,
                requires_approval=True,
                max_retries=3,
            ),
            run_control_tests_on_search,
            create_workbench_gene_set,
            Tool(run_gene_set_enrichment, sequential=True, max_retries=3),
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
            request_search_inspection,
            think,
            search_memory,
            remember,
        ],
    )
    return DynamicEnumToolset(
        wrapped=base,
        build_overrides=_verification_enum_overrides,
    )
