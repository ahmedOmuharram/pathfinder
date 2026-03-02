"""Parameter optimization for VEuPathDB searches.

Re-exports the public API so existing ``from
veupath_chatbot.services.parameter_optimization import ...`` statements
continue to work unchanged.
"""

from veupath_chatbot.services.parameter_optimization.config import (
    CancelCheck,
    OptimizationConfig,
    OptimizationMethod,
    OptimizationResult,
    ParameterSpec,
    ProgressCallback,
    TrialResult,
)
from veupath_chatbot.services.parameter_optimization.core import (
    optimize_search_parameters,
)
from veupath_chatbot.services.parameter_optimization.scoring import (
    _compute_pareto_frontier,
    _compute_score,
    _compute_sensitivity,
    _trial_to_json,
    result_to_json,
)

__all__ = [
    "CancelCheck",
    "OptimizationConfig",
    "OptimizationMethod",
    "OptimizationResult",
    "ParameterSpec",
    "ProgressCallback",
    "TrialResult",
    "_compute_pareto_frontier",
    "_compute_score",
    "_compute_sensitivity",
    "_trial_to_json",
    "optimize_search_parameters",
    "result_to_json",
]
