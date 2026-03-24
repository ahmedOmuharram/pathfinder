"""Parameter optimization for VEuPathDB searches.

Re-exports the public API so callers can do
``from veupath_chatbot.services.parameter_optimization import ...``.
"""

from veupath_chatbot.services.parameter_optimization.config import (
    CancelCheck,
    OptimizationConfig,
    OptimizationInput,
    OptimizationMethod,
    OptimizationResult,
    ParameterSpec,
    ProgressCallback,
    TrialResult,
)
from veupath_chatbot.services.parameter_optimization.core import (
    optimize_search_parameters,
)

__all__ = [
    "CancelCheck",
    "OptimizationConfig",
    "OptimizationInput",
    "OptimizationMethod",
    "OptimizationResult",
    "ParameterSpec",
    "ProgressCallback",
    "TrialResult",
    "optimize_search_parameters",
]
