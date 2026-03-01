"""Step decomposition analysis for multi-step strategies.

Replaces the Optuna-based tree optimization with four interpretable
analysis phases that give researchers actionable, per-step insights:

1. **Per-step evaluation** -- evaluate each leaf independently.
2. **Operator comparison** -- try all operators at each combine node.
3. **Step contribution (ablation)** -- measure the impact of removing each leaf.
4. **Parameter sensitivity** -- sweep numeric params across their range.
"""

from veupath_chatbot.services.experiment.step_analysis._evaluation import (
    run_controls_against_tree,
)
from veupath_chatbot.services.experiment.step_analysis.orchestrator import (
    run_step_analysis,
)

__all__ = [
    "run_controls_against_tree",
    "run_step_analysis",
]
