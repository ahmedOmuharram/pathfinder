"""Tests for _auto_expand_organism_param in step creation.

Verifies that GenesByOrthologPattern's organism parameter gets auto-expanded
to all leaf organism values when the model passes an incomplete set.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from veupath_chatbot.services.strategies.step_creation import (
    _auto_expand_organism_param,
)

# Minimal WDK-shaped organism vocabulary tree (3 leaves)
MOCK_ORGANISM_VOCAB = {
    "data": {"display": "@@fake@@", "term": "@@fake@@"},
    "children": [
        {
            "data": {"display": "Arthropoda", "term": "Arthropoda"},
            "children": [
                {
                    "data": {
                        "display": "Anopheles gambiae PEST",
                        "term": "Anopheles gambiae PEST",
                    },
                    "children": [],
                },
                {
                    "data": {
                        "display": "Aedes aegypti LVP_AGWG",
                        "term": "Aedes aegypti LVP_AGWG",
                    },
                    "children": [],
                },
            ],
        },
        {
            "data": {
                "display": "Culex quinquefasciatus JHB 2020",
                "term": "Culex quinquefasciatus JHB 2020",
            },
            "children": [],
        },
    ],
}

# Fake expandParams response matching WDK shape
MOCK_SEARCH_DETAILS = {
    "searchData": {
        "parameters": [
            {
                "name": "organism",
                "type": "multi-pick-vocabulary",
                "vocabulary": MOCK_ORGANISM_VOCAB,
            },
            {
                "name": "profile_pattern",
                "type": "string",
            },
        ]
    }
}


def _mock_discovery():
    """Build a mock discovery service that returns MOCK_SEARCH_DETAILS."""
    svc = AsyncMock()
    svc.get_search_details = AsyncMock(return_value=MOCK_SEARCH_DETAILS)
    return svc


class TestAutoExpandOrganism:
    """Unit tests for _auto_expand_organism_param."""

    @pytest.mark.asyncio
    async def test_expands_single_organism_to_all_leaves(self):
        params = {
            "profile_pattern": "agam>=1T",
            "organism": '["Anopheles gambiae PEST"]',
        }
        with patch(
            "veupath_chatbot.integrations.veupathdb.discovery.get_discovery_service",
            return_value=_mock_discovery(),
        ):
            result = await _auto_expand_organism_param(
                "vectorbase", "transcript", params
            )

        orgs = json.loads(result["organism"])
        assert len(orgs) == 3
        assert "Anopheles gambiae PEST" in orgs
        assert "Aedes aegypti LVP_AGWG" in orgs
        assert "Culex quinquefasciatus JHB 2020" in orgs

    @pytest.mark.asyncio
    async def test_expands_empty_organism(self):
        params = {"profile_pattern": "agam>=1T", "organism": "[]"}
        with patch(
            "veupath_chatbot.integrations.veupathdb.discovery.get_discovery_service",
            return_value=_mock_discovery(),
        ):
            result = await _auto_expand_organism_param(
                "vectorbase", "transcript", params
            )

        orgs = json.loads(result["organism"])
        assert len(orgs) == 3

    @pytest.mark.asyncio
    async def test_expands_fake_sentinel(self):
        """@@fake@@ is not a real organism — should be replaced with all leaves."""
        params = {"profile_pattern": "agam>=1T", "organism": '["@@fake@@"]'}
        with patch(
            "veupath_chatbot.integrations.veupathdb.discovery.get_discovery_service",
            return_value=_mock_discovery(),
        ):
            result = await _auto_expand_organism_param(
                "vectorbase", "transcript", params
            )

        orgs = json.loads(result["organism"])
        assert "@@fake@@" not in orgs
        assert len(orgs) == 3

    @pytest.mark.asyncio
    async def test_skips_expansion_when_many_organisms(self):
        """If >5 organisms already selected, don't re-expand."""
        many_orgs = [f"Organism {i}" for i in range(10)]
        params = {"profile_pattern": "agam>=1T", "organism": json.dumps(many_orgs)}
        with patch(
            "veupath_chatbot.integrations.veupathdb.discovery.get_discovery_service",
            return_value=_mock_discovery(),
        ):
            result = await _auto_expand_organism_param(
                "vectorbase", "transcript", params
            )

        orgs = json.loads(result["organism"])
        assert len(orgs) == 10  # unchanged

    @pytest.mark.asyncio
    async def test_preserves_other_params(self):
        params = {
            "profile_pattern": "agam>=1T,aaeg>=1T",
            "organism": '["Anopheles gambiae PEST"]',
            "included_species": "some value",
        }
        with patch(
            "veupath_chatbot.integrations.veupathdb.discovery.get_discovery_service",
            return_value=_mock_discovery(),
        ):
            result = await _auto_expand_organism_param(
                "vectorbase", "transcript", params
            )

        assert result["profile_pattern"] == "agam>=1T,aaeg>=1T"
        assert result["included_species"] == "some value"

    @pytest.mark.asyncio
    async def test_handles_organism_as_list(self):
        """Organism can be a Python list, not just a JSON string."""
        params = {"profile_pattern": "agam>=1T", "organism": ["Anopheles gambiae PEST"]}
        with patch(
            "veupath_chatbot.integrations.veupathdb.discovery.get_discovery_service",
            return_value=_mock_discovery(),
        ):
            result = await _auto_expand_organism_param(
                "vectorbase", "transcript", params
            )

        orgs = json.loads(result["organism"])
        assert len(orgs) == 3

    @pytest.mark.asyncio
    async def test_handles_missing_organism_param(self):
        params = {"profile_pattern": "agam>=1T"}
        with patch(
            "veupath_chatbot.integrations.veupathdb.discovery.get_discovery_service",
            return_value=_mock_discovery(),
        ):
            result = await _auto_expand_organism_param(
                "vectorbase", "transcript", params
            )

        orgs = json.loads(result["organism"])
        assert len(orgs) == 3

    @pytest.mark.asyncio
    async def test_graceful_on_discovery_failure(self):
        """If discovery service fails, return params unchanged."""
        params = {"profile_pattern": "agam>=1T", "organism": '["one"]'}
        mock_svc = AsyncMock()
        mock_svc.get_search_details = AsyncMock(side_effect=Exception("network error"))
        with patch(
            "veupath_chatbot.integrations.veupathdb.discovery.get_discovery_service",
            return_value=mock_svc,
        ):
            result = await _auto_expand_organism_param(
                "vectorbase", "transcript", params
            )

        assert result["organism"] == '["one"]'  # unchanged

    @pytest.mark.asyncio
    async def test_excludes_fake_sentinel_from_leaves(self):
        """The @@fake@@ root node should never appear in expanded leaves."""
        params = {"profile_pattern": "agam>=1T", "organism": "[]"}
        with patch(
            "veupath_chatbot.integrations.veupathdb.discovery.get_discovery_service",
            return_value=_mock_discovery(),
        ):
            result = await _auto_expand_organism_param(
                "vectorbase", "transcript", params
            )

        orgs = json.loads(result["organism"])
        assert "@@fake@@" not in orgs
