from uuid import UUID, uuid4

import httpx

from pathfinder.services.experiment.store import get_experiment_store
from pathfinder.services.experiment.types.experiment import (
    Experiment,
    ExperimentConfig,
)


def _make_experiment(
    user_id: UUID, exp_id: str, *, wdk_step_id: int | None = None
) -> Experiment:
    return Experiment(
        id=exp_id,
        user_id=str(user_id),
        config=ExperimentConfig(
            site_id="plasmodb",
            record_type="transcript",
            search_name="GenesByTaxon",
            parameters={},
            positive_controls=["PF3D7_0100100"],
            negative_controls=[],
            controls_search_name="GenesByGeneList",
            controls_param_name="ds_gene_ids",
        ),
        wdk_step_id=wdk_step_id,
    )


async def test_results_attributes_404_when_experiment_missing(
    authed_client: httpx.AsyncClient, authed_user_id: UUID
) -> None:
    del authed_user_id
    resp = await authed_client.get(
        "/api/v1/experiments/exp_does_not_exist/results/attributes"
    )
    assert resp.status_code == 404, resp.text
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_results_attributes_403_for_other_users_experiment(
    authed_client: httpx.AsyncClient, authed_user_id: UUID
) -> None:
    """Ownership is enforced before any WDK work: another user's experiment
    is forbidden, not silently served."""
    del authed_user_id
    exp_id = f"exp_{uuid4().hex[:10]}"
    get_experiment_store().save(_make_experiment(uuid4(), exp_id, wdk_step_id=5))

    resp = await authed_client.get(f"/api/v1/experiments/{exp_id}/results/attributes")

    assert resp.status_code == 403, resp.text


async def test_refine_rejects_an_operator_wdk_does_not_have(
    authed_client: httpx.AsyncClient, authed_user_id: UUID
) -> None:
    """A typo in the operator is a 422, not a trip to WDK.

    The field was a plain str, so an unknown operator was carried all the
    way into the boolean search config and came back as an opaque WDK error.
    """
    exp_id = f"exp_{uuid4().hex[:10]}"
    get_experiment_store().save(_make_experiment(authed_user_id, exp_id, wdk_step_id=1))

    resp = await authed_client.post(
        f"/api/v1/experiments/{exp_id}/refine",
        json={
            "action": "combine",
            "searchName": "GenesByTaxon",
            "operator": "INTERSCET",
        },
    )

    assert resp.status_code == 422, resp.text
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_refine_rejects_colocate_as_a_boolean_operator(
    authed_client: httpx.AsyncClient, authed_user_id: UUID
) -> None:
    # COLOCATE is a CombineOp but WDK does colocation through
    # GenesBySpanLogic, so it must not reach the boolean search.
    exp_id = f"exp_{uuid4().hex[:10]}"
    get_experiment_store().save(_make_experiment(authed_user_id, exp_id, wdk_step_id=1))

    resp = await authed_client.post(
        f"/api/v1/experiments/{exp_id}/refine",
        json={
            "action": "combine",
            "searchName": "GenesByTaxon",
            "operator": "COLOCATE",
        },
    )

    assert resp.status_code == 422, resp.text
