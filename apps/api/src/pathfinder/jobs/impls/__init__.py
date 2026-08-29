"""Worker-side durable tool implementations.

The worker calls :func:`register_all_tools` from its ``amain`` entrypoint so
that every durable tool's real body is in ``TOOL_REGISTRY`` before it starts
pulling jobs off the queue. Agent-side wrappers simply submit the job and
``interrupt()`` — the true work runs here on the worker.
"""

from __future__ import annotations

from pathfinder.jobs import tasks
from pathfinder.jobs.impls.control_tests_impl import (
    run_control_tests_on_step_impl,
)
from pathfinder.jobs.impls.eda_compute_impl import run_eda_compute_impl
from pathfinder.jobs.impls.geneset_enrichment_impl import (
    run_gene_set_enrichment_impl,
)
from pathfinder.jobs.impls.optimize_params_impl import (
    optimize_search_parameters_impl,
)
from pathfinder.jobs.registry import register_tool


def register_all_tools() -> None:
    """Register every durable tool implementation.

    Also fires ``tasks.ensure_registered`` so the ``@procrastinate_app.task``
    decorators in ``pathfinder.jobs.tasks`` run (as an import side effect)
    before the worker starts pulling jobs. Safe to call repeatedly.
    """
    tasks.ensure_registered()
    register_tool("run_control_tests_on_step", run_control_tests_on_step_impl)
    register_tool("optimize_search_parameters", optimize_search_parameters_impl)
    register_tool("geneset_enrichment", run_gene_set_enrichment_impl)
    register_tool("run_eda_compute", run_eda_compute_impl)
