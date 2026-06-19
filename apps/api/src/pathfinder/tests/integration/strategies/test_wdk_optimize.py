from __future__ import annotations

import pytest

from pathfinder.domain.parameters.values import MultiPickValue, StringValue
from pathfinder.services.parameter_optimization.config import (
    OptimizationConfig,
    OptimizationInput,
    ParameterSpec,
)
from pathfinder.services.parameter_optimization.core import optimize_search_parameters

pytestmark = [pytest.mark.live_wdk, pytest.mark.asyncio]

_ORGANISM = "Plasmodium falciparum 3D7"

# A subset of GO:0004672-curated kinases (positive controls); the EC search is
# optimized to best recover them, so target (EC) != controls (GO) — non-circular.
_KINASE_CONTROLS = [
    "PF3D7_0102600",
    "PF3D7_0217500",
    "PF3D7_0309200",
    "PF3D7_0311400",
    "PF3D7_0420100",
    "PF3D7_0500900",
    "PF3D7_0605300",
    "PF3D7_0717500",
    "PF3D7_0934800",
    "PF3D7_1108400",
    "PF3D7_1121300",
    "PF3D7_1201600",
    "PF3D7_1238900",
    "PF3D7_1337100",
    "PF3D7_1436600",
    "PF3D7_1444500",
]


async def test_grid_sweep_scores_ec_variants_against_kinase_controls(
    wdk_session: None,
) -> None:
    del wdk_session
    inp = OptimizationInput(
        site_id="plasmodb",
        record_type="transcript",
        search_name="GenesByEcNumber",
        parameter_space=[
            ParameterSpec(
                name="ec_number_pattern",
                type="categorical",
                choices=["2.7.11.1", "2.7.1.-"],
            )
        ],
        controls_search_name="GeneByLocusTag",
        controls_param_name="ds_gene_ids",
        fixed_parameters={
            "organism": MultiPickValue(values=[_ORGANISM]),
            "ec_source": MultiPickValue(values=["GeneDB", "KEGG_Enzyme", "GenBank"]),
            "ec_wildcard": StringValue(value="N/A"),
        },
        positive_controls=_KINASE_CONTROLS,
    )

    result = await optimize_search_parameters(
        inp, OptimizationConfig(budget=2, method="grid", objective="recall")
    )

    assert result.status == "completed", result.error_message
    assert len(result.all_trials) == 2
    for trial in result.all_trials:
        assert trial.recall is not None
        assert 0.0 <= trial.recall <= 1.0
        assert "ec_number_pattern" in trial.parameters
    assert result.best_trial is not None
    assert result.best_trial.score == max(t.score for t in result.all_trials)
    # The EC-2.7.11.1 (protein-kinase) variant recovers more GO kinases than
    # the broader 2.7.1.- variant — the sweep picks the better recall.
    assert result.best_trial.recall is not None
    assert result.best_trial.recall >= 0.3
    assert set(result.sensitivity) == {"ec_number_pattern"}
