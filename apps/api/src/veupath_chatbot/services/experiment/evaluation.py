"""Evaluation service: single re-evaluation of an experiment.

Pure business logic extracted from the transport handler. No HTTP/SSE
concerns here -- callers (routers, tools, etc.) wrap the results in
whatever transport format they need.

Threshold sweep orchestration lives in ``sweep_service.py``.
"""

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.platform.errors import DataParsingError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_tests import (
    IntersectionConfig,
    run_positive_negative_controls,
)
from veupath_chatbot.services.experiment.helpers import (
    ControlsContext,
    extract_and_enrich_genes,
)
from veupath_chatbot.services.experiment.metrics import metrics_from_control_result
from veupath_chatbot.services.experiment.step_analysis import (
    run_controls_against_tree,
)
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import (
    Experiment,
    experiment_to_json,
)

logger = get_logger(__name__)


async def re_evaluate(exp: Experiment) -> JSONObject:
    """Re-run control evaluation against the (possibly modified) strategy.

    Updates the experiment in-place (metrics + gene lists) and persists it.
    Returns the full experiment JSON.
    """
    ctx = ControlsContext.from_config(exp.config)
    if exp.config.is_tree_mode:
        step_tree = exp.config.step_tree
        if not isinstance(step_tree, PlanStepNode):
            msg = "step_tree must be a PlanStepNode in tree mode"
            raise DataParsingError(msg)

        result = await run_controls_against_tree(ctx, step_tree)
    else:
        result = await run_positive_negative_controls(
            IntersectionConfig.from_experiment_config(exp.config),
            positive_controls=ctx.positive_controls or None,
            negative_controls=ctx.negative_controls or None,
        )

    metrics = metrics_from_control_result(result)
    exp.metrics = metrics
    (
        exp.true_positive_genes,
        exp.false_negative_genes,
        exp.false_positive_genes,
        exp.true_negative_genes,
    ) = await extract_and_enrich_genes(
        site_id=exp.config.site_id,
        result=result,
        negative_controls=exp.config.negative_controls,
    )
    get_experiment_store().save(exp)

    return experiment_to_json(exp)
