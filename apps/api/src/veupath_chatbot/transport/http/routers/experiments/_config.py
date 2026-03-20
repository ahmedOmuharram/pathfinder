"""Build ExperimentConfig from HTTP request DTOs.

This is a transport-layer adapter: it converts the HTTP-specific
``CreateExperimentRequest`` Pydantic model into the service-layer
``ExperimentConfig`` dataclass.  Lives here (not in services/) because
it depends on transport schemas.
"""

from veupath_chatbot.services.experiment.types import (
    ExperimentConfig,
    OperatorKnob,
    OptimizationSpec,
    ThresholdKnob,
)
from veupath_chatbot.transport.http.schemas.experiments import CreateExperimentRequest


def config_from_request(req: CreateExperimentRequest) -> ExperimentConfig:
    """Build :class:`ExperimentConfig` from a create request DTO."""
    opt_specs = None
    if req.optimization_specs:
        opt_specs = [
            OptimizationSpec(
                name=s.name,
                type=s.type,
                min=s.min,
                max=s.max,
                step=s.step,
                choices=s.choices,
            )
            for s in req.optimization_specs
        ]
    return ExperimentConfig(
        site_id=req.site_id,
        record_type=req.record_type,
        mode=req.mode,
        search_name=req.search_name,
        parameters=req.parameters,
        step_tree=req.step_tree,
        source_strategy_id=req.source_strategy_id,
        optimization_target_step=req.optimization_target_step,
        positive_controls=req.positive_controls,
        negative_controls=req.negative_controls,
        controls_search_name=req.controls_search_name,
        controls_param_name=req.controls_param_name,
        controls_value_format=req.controls_value_format,
        enable_cross_validation=req.enable_cross_validation,
        k_folds=req.k_folds,
        enrichment_types=list(req.enrichment_types),
        name=req.name,
        description=req.description,
        optimization_specs=opt_specs,
        optimization_budget=req.optimization_budget,
        optimization_objective=req.optimization_objective or "balanced_accuracy",
        parameter_display_values=(
            {str(k): str(v) for k, v in req.parameter_display_values.items()}
            if req.parameter_display_values
            else None
        ),
        enable_step_analysis=req.enable_step_analysis,
        step_analysis_phases=(
            req.step_analysis_phases
            or [
                "step_evaluation",
                "operator_comparison",
                "contribution",
                "sensitivity",
            ]
        ),
        control_set_id=req.control_set_id,
        threshold_knobs=[
            ThresholdKnob(
                step_id=k.step_id,
                param_name=k.param_name,
                min_val=k.min_val,
                max_val=k.max_val,
                step_size=k.step_size,
            )
            for k in (req.threshold_knobs or [])
        ]
        or None,
        operator_knobs=[
            OperatorKnob(
                combine_node_id=k.combine_node_id,
                options=k.options,
            )
            for k in (req.operator_knobs or [])
        ]
        or None,
        tree_optimization_objective=req.tree_optimization_objective,
        tree_optimization_budget=req.tree_optimization_budget,
        max_list_size=req.max_list_size,
        sort_attribute=req.sort_attribute,
        sort_direction=req.sort_direction,
        parent_experiment_id=req.parent_experiment_id,
        target_gene_ids=req.target_gene_ids,
    )
