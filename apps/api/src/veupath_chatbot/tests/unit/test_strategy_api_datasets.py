"""Unit tests for veupath_chatbot.integrations.veupathdb.strategy_api.datasets.

Tests DatasetsMixin: create_dataset with typed WDKDatasetConfig input.
Validates that WDKIdentifier.model_validate replaces the old isinstance guards.
"""

from unittest.mock import AsyncMock, MagicMock

import pydantic
import pytest

from veupath_chatbot.integrations.veupathdb.strategy_api.datasets import DatasetsMixin
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKDatasetConfigIdList,
    WDKDatasetIdListContent,
)


def _make_mixin(user_id: str = "12345") -> tuple[DatasetsMixin, MagicMock]:
    """Create DatasetsMixin with a mock client, pre-initialized session."""
    client = MagicMock()
    client.post = AsyncMock()
    mixin = DatasetsMixin(client, user_id=user_id)
    mixin._session_initialized = True
    return mixin, client


def _id_list_config(ids: list[str]) -> WDKDatasetConfigIdList:
    """Build a WDKDatasetConfigIdList for testing."""
    return WDKDatasetConfigIdList(
        source_type="idList",
        source_content=WDKDatasetIdListContent(ids=ids),
    )


class TestCreateDataset:
    """Dataset creation via DatasetsMixin with typed config."""

    async def test_creates_dataset_and_returns_id(self) -> None:
        mixin, client = _make_mixin()
        client.post.return_value = {"id": 999}

        config = _id_list_config(["PF3D7_0100100", "PF3D7_0200200"])
        ds_id = await mixin.create_dataset(config)

        assert ds_id == 999
        payload = client.post.call_args.kwargs["json"]
        assert payload["sourceType"] == "idList"
        assert payload["sourceContent"]["ids"] == ["PF3D7_0100100", "PF3D7_0200200"]

    async def test_posts_to_correct_url(self) -> None:
        mixin, client = _make_mixin(user_id="42")
        client.post.return_value = {"id": 1}

        config = _id_list_config(["GENE_A"])
        await mixin.create_dataset(config)

        url = client.post.call_args.args[0]
        assert url == "/users/42/datasets"

    async def test_raises_on_missing_id_in_response(self) -> None:
        mixin, client = _make_mixin()
        client.post.return_value = {"status": "created"}

        config = _id_list_config(["PF3D7_0100100"])
        with pytest.raises(pydantic.ValidationError):
            await mixin.create_dataset(config)

    async def test_raises_on_non_int_id(self) -> None:
        mixin, client = _make_mixin()
        client.post.return_value = {"id": "not_an_int"}

        config = _id_list_config(["PF3D7_0100100"])
        with pytest.raises(pydantic.ValidationError):
            await mixin.create_dataset(config)

    async def test_raises_on_non_dict_response(self) -> None:
        mixin, client = _make_mixin()
        client.post.return_value = []

        config = _id_list_config(["PF3D7_0100100"])
        with pytest.raises(pydantic.ValidationError):
            await mixin.create_dataset(config)

    async def test_uses_user_id_override(self) -> None:
        mixin, client = _make_mixin(user_id="12345")
        client.post.return_value = {"id": 1}

        config = _id_list_config(["GENE_A"])
        await mixin.create_dataset(config, user_id="99999")

        url = client.post.call_args.args[0]
        assert url == "/users/99999/datasets"
