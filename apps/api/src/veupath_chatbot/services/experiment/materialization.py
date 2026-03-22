"""WDK strategy materialization for experiments.

Creates, persists, and cleans up WDK strategies from experiment configs,
including step tree materialization for multi-step and import modes.
"""

from veupath_chatbot.domain.strategy.ast import StepTreeNode
from veupath_chatbot.domain.strategy.ops import DEFAULT_COMBINE_OPERATOR
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKStepTree
from veupath_chatbot.platform.errors import (
    AppError,
    ValidationError,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.types import (
    Experiment,
    ExperimentConfig,
)

logger = get_logger(__name__)


async def _materialize_step_tree(
    api: StrategyAPI,
    node: JSONObject,
    record_type: str,
    *,
    site_id: str = "",
) -> StepTreeNode:
    """Recursively create WDK steps from a ``PlanStepNode`` dict.

    Walks the tree bottom-up: leaf search nodes are created first,
    then combine/transform nodes reference them.

    :param api: Strategy API instance.
    :param node: ``PlanStepNode``-shaped dict.
    :param record_type: WDK record type for all steps.
    :param site_id: VEuPathDB site identifier (for param auto-expansion).
    :returns: :class:`StepTreeNode` ready for strategy creation.
    """
    primary_node = node.get("primaryInput")
    secondary_node = node.get("secondaryInput")

    primary_tree: StepTreeNode | None = None
    secondary_tree: StepTreeNode | None = None

    if isinstance(primary_node, dict):
        primary_tree = await _materialize_step_tree(
            api, primary_node, record_type, site_id=site_id
        )
    if isinstance(secondary_node, dict):
        secondary_tree = await _materialize_step_tree(
            api, secondary_node, record_type, site_id=site_id
        )

    search_name = str(node.get("searchName", ""))
    raw_params = node.get("parameters")
    parameters: JSONObject = raw_params if isinstance(raw_params, dict) else {}
    display_name = str(node.get("displayName", search_name))

    if primary_tree is not None and secondary_tree is not None:
        operator = str(node.get("operator", DEFAULT_COMBINE_OPERATOR.value))
        if operator == "COLOCATE":
            # Colocation uses GenesBySpanLogic — two input-step params
            # (span_a, span_b) wired via stepTree at strategy creation.
            coloc_raw = node.get("colocationParams")
            upstream = "0"
            downstream = "0"
            if isinstance(coloc_raw, dict):
                upstream = str(coloc_raw.get("upstream", 0))
                downstream = str(coloc_raw.get("downstream", 0))
            coloc_params: JSONObject = {
                "span_sentence": "sentence",
                "span_operation": "overlap",
                "span_strand": "Both strands",
                "span_output": "a",
                "region_a": "upstream",
                "region_b": "exact",
                "span_begin_a": "start",
                "span_begin_direction_a": "-",
                "span_begin_offset_a": upstream,
                "span_end_a": "start",
                "span_end_direction_a": "-",
                "span_end_offset_a": downstream,
                "span_begin_b": "start",
                "span_begin_direction_b": "-",
                "span_begin_offset_b": "0",
                "span_end_b": "stop",
                "span_end_direction_b": "-",
                "span_end_offset_b": "0",
            }
            step = await api.create_transform_step(
                input_step_id=primary_tree.step_id,
                transform_name="GenesBySpanLogic",
                parameters=coloc_params,
                record_type=record_type,
                custom_name=display_name,
            )
        else:
            step = await api.create_combined_step(
                primary_step_id=primary_tree.step_id,
                secondary_step_id=secondary_tree.step_id,
                boolean_operator=operator,
                record_type=record_type,
                custom_name=display_name,
            )
        step_id = step.id
        return StepTreeNode(
            step_id=step_id, primary_input=primary_tree, secondary_input=secondary_tree
        )
    if primary_tree is not None:
        step = await api.create_transform_step(
            input_step_id=primary_tree.step_id,
            transform_name=search_name,
            parameters=parameters,
            record_type=record_type,
            custom_name=display_name,
        )
        step_id = step.id
        return StepTreeNode(step_id=step_id, primary_input=primary_tree)
    step = await api.create_step(
        record_type=record_type,
        search_name=search_name,
        parameters=parameters,
        custom_name=display_name,
    )
    step_id = step.id
    return StepTreeNode(step_id=step_id)


async def _persist_experiment_strategy(
    config: ExperimentConfig,
    experiment_id: str,
    *,
    override_tree: JSONObject | None = None,
) -> JSONObject:
    """Create a persisted WDK strategy for result exploration.

    Handles all experiment modes:

    * **single**: one search step.
    * **multi-step**: recursively materialise the ``step_tree``.
    * **import**: duplicate the step tree from an existing WDK strategy.

    :param config: Experiment configuration.
    :param experiment_id: Unique experiment identifier.
    :param override_tree: If provided, materialise this tree instead of the
        config's ``step_tree`` (used after tree optimisation).
    :returns: Dict with ``strategy_id`` and ``step_id``.
    """
    api = get_strategy_api(config.site_id)
    mode = config.mode or "single"

    if mode == "import" and config.source_strategy_id and override_tree is None:
        return await _persist_import_strategy(api, config, experiment_id)

    effective_tree = override_tree or (
        config.step_tree if isinstance(config.step_tree, dict) else None
    )
    if mode in ("multi-step", "import") and isinstance(effective_tree, dict):
        root_tree = await _materialize_step_tree(
            api, effective_tree, config.record_type, site_id=config.site_id
        )
    else:
        step_payload = await api.create_step(
            record_type=config.record_type,
            search_name=config.search_name,
            parameters=config.parameters or {},
            custom_name=f"Experiment: {config.name}",
        )
        step_id = step_payload.id
        root_tree = StepTreeNode(step_id=step_id)

    created = await api.create_strategy(
        step_tree=root_tree,
        name=f"exp:{experiment_id}",
        description=f"Persisted strategy for experiment {config.name}",
        is_internal=True,
    )
    strategy_id = created.id

    logger.info(
        "Persisted WDK strategy for experiment",
        experiment_id=experiment_id,
        strategy_id=strategy_id,
        step_id=root_tree.step_id,
    )
    return {"strategy_id": strategy_id, "step_id": root_tree.step_id}


async def _persist_import_strategy(
    api: StrategyAPI,
    config: ExperimentConfig,
    experiment_id: str,
) -> JSONObject:
    """Import an existing WDK strategy by duplicating its step tree.

    Uses the WDK ``duplicated-step-tree`` endpoint to copy the source
    strategy's step tree into a new set of unattached steps.

    :param api: Strategy API instance.
    :param config: Experiment configuration (must have ``source_strategy_id``).
    :param experiment_id: Unique experiment identifier.
    :returns: Dict with ``strategy_id`` and ``step_id``.
    """
    if not config.source_strategy_id:
        msg = "source_strategy_id is required for import mode"
        raise ValidationError(detail=msg)
    source_id = int(config.source_strategy_id)

    dup_tree = await api.get_duplicated_step_tree(source_id)

    # The duplicated tree already has real WDK step IDs, so we can
    # directly wrap it in a StepTreeNode.
    def _wdk_tree_to_node(tree: WDKStepTree) -> StepTreeNode:
        sid = tree.step_id
        primary = tree.primary_input
        secondary = tree.secondary_input
        return StepTreeNode(
            step_id=sid,
            primary_input=_wdk_tree_to_node(primary) if primary is not None else None,
            secondary_input=_wdk_tree_to_node(secondary)
            if secondary is not None
            else None,
        )

    root = _wdk_tree_to_node(dup_tree)

    created = await api.create_strategy(
        step_tree=root,
        name=f"exp:{experiment_id}",
        description=f"Imported strategy for experiment {config.name}",
        is_internal=True,
    )
    strategy_id = created.id

    logger.info(
        "Persisted imported WDK strategy for experiment",
        experiment_id=experiment_id,
        strategy_id=strategy_id,
        step_id=root.step_id,
    )
    return {"strategy_id": strategy_id, "step_id": root.step_id}


async def cleanup_experiment_strategy(experiment: Experiment) -> None:
    """Delete the persisted WDK strategy when an experiment is deleted.

    :param experiment: Experiment whose WDK strategy should be cleaned up.
    """
    if experiment.wdk_strategy_id is None:
        return
    try:
        api = get_strategy_api(experiment.config.site_id)
        await api.delete_strategy(experiment.wdk_strategy_id)
        logger.info(
            "Deleted WDK strategy for experiment",
            experiment_id=experiment.id,
            strategy_id=experiment.wdk_strategy_id,
        )
    except AppError as exc:
        logger.warning(
            "Failed to delete WDK strategy during experiment cleanup",
            experiment_id=experiment.id,
            strategy_id=experiment.wdk_strategy_id,
            error=str(exc),
        )
