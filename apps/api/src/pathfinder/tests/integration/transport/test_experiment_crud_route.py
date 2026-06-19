from uuid import UUID, uuid4

import httpx

from pathfinder.services.experiment.store import get_experiment_store
from pathfinder.services.experiment.types.experiment import (
    Experiment,
    ExperimentConfig,
)


def _make_experiment(
    user_id: UUID,
    exp_id: str,
    *,
    site_id: str = "plasmodb",
) -> Experiment:
    return Experiment(
        id=exp_id,
        user_id=str(user_id),
        config=ExperimentConfig(
            site_id=site_id,
            record_type="transcript",
            search_name="GenesByTaxon",
            parameters={},
            positive_controls=["PF3D7_0100100", "PF3D7_0100200"],
            negative_controls=[],
            controls_search_name="GenesByGeneList",
            controls_param_name="ds_gene_ids",
        ),
    )


def _new_id() -> str:
    return f"exp_{uuid4().hex[:10]}"


async def test_list_filters_by_site_and_owner(
    authed_client: httpx.AsyncClient, authed_user_id: UUID
) -> None:
    mine_plasmo = _new_id()
    mine_toxo = _new_id()
    other = _new_id()
    store = get_experiment_store()
    store.save(_make_experiment(authed_user_id, mine_plasmo, site_id="plasmodb"))
    store.save(_make_experiment(authed_user_id, mine_toxo, site_id="toxodb"))
    store.save(_make_experiment(uuid4(), other, site_id="plasmodb"))

    resp = await authed_client.get(
        "/api/v1/experiments/", params={"siteId": "plasmodb"}
    )
    assert resp.status_code == 200, resp.text
    ids = {e["id"] for e in resp.json()}
    assert mine_plasmo in ids
    assert mine_toxo not in ids
    assert other not in ids

    mine = next(e for e in resp.json() if e["id"] == mine_plasmo)
    assert mine["siteId"] == "plasmodb"
    assert mine["searchName"] == "GenesByTaxon"
    assert mine["recordType"] == "transcript"
    assert mine["totalPositives"] == 2


async def test_get_returns_full_detail(
    authed_client: httpx.AsyncClient, authed_user_id: UUID
) -> None:
    exp_id = _new_id()
    get_experiment_store().save(_make_experiment(authed_user_id, exp_id))

    resp = await authed_client.get(f"/api/v1/experiments/{exp_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == exp_id
    assert body["status"] == "pending"
    assert body["notes"] is None


async def test_patch_notes_persists(
    authed_client: httpx.AsyncClient, authed_user_id: UUID
) -> None:
    exp_id = _new_id()
    get_experiment_store().save(_make_experiment(authed_user_id, exp_id))

    patched = await authed_client.patch(
        f"/api/v1/experiments/{exp_id}", json={"notes": "promising hit rate"}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["notes"] == "promising hit rate"

    again = await authed_client.get(f"/api/v1/experiments/{exp_id}")
    assert again.json()["notes"] == "promising hit rate"


async def test_delete_removes_experiment(
    authed_client: httpx.AsyncClient, authed_user_id: UUID
) -> None:
    exp_id = _new_id()
    get_experiment_store().save(_make_experiment(authed_user_id, exp_id))

    deleted = await authed_client.delete(f"/api/v1/experiments/{exp_id}")
    assert deleted.status_code == 204, deleted.text

    gone = await authed_client.get(f"/api/v1/experiments/{exp_id}")
    assert gone.status_code == 404


async def test_other_users_experiment_is_forbidden(
    authed_client: httpx.AsyncClient, authed_user_id: UUID
) -> None:
    del authed_user_id
    exp_id = _new_id()
    get_experiment_store().save(_make_experiment(uuid4(), exp_id))

    assert (await authed_client.get(f"/api/v1/experiments/{exp_id}")).status_code == 403
    patch = await authed_client.patch(
        f"/api/v1/experiments/{exp_id}", json={"notes": "x"}
    )
    assert patch.status_code == 403
    assert (
        await authed_client.delete(f"/api/v1/experiments/{exp_id}")
    ).status_code == 403
