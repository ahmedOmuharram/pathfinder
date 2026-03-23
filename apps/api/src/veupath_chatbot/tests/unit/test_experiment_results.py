"""Tests for experiment result helpers."""

from veupath_chatbot.integrations.veupathdb.wdk_models import WDKRecordInstance
from veupath_chatbot.services.wdk.helpers import (
    extract_pk,
    order_primary_key,
)


class TestExtractPk:
    def test_extracts_first_value(self):
        record = WDKRecordInstance(id=[{"name": "source_id", "value": "PF3D7_0100100"}])
        assert extract_pk(record) == "PF3D7_0100100"

    def test_strips_whitespace(self):
        record = WDKRecordInstance(
            id=[{"name": "source_id", "value": "  PF3D7_0100100  "}]
        )
        assert extract_pk(record) == "PF3D7_0100100"

    def test_returns_none_for_empty_list(self):
        record = WDKRecordInstance(id=[])
        assert extract_pk(record) is None

    def test_returns_none_for_no_id(self):
        record = WDKRecordInstance()
        assert extract_pk(record) is None


class TestOrderPrimaryKey:
    """WDK requires PK columns in the exact order of primaryKeyColumnRefs.

    Per VEuPathDB/WDK RecordRequest.java, the primary key array order
    must match the record class definition.
    """

    def test_reorders_to_match_refs(self):
        """PK parts sent in wrong order are reordered to match record class."""
        pk_parts = [
            {"name": "project_id", "value": "PlasmoDB"},
            {"name": "source_id", "value": "PF3D7_0100100"},
        ]
        pk_refs = ["source_id", "project_id"]
        result = order_primary_key(pk_parts, pk_refs, pk_defaults={})
        assert result == [
            {"name": "source_id", "value": "PF3D7_0100100"},
            {"name": "project_id", "value": "PlasmoDB"},
        ]

    def test_fills_missing_project_id(self):
        """Missing project_id is filled from pk_defaults."""
        pk_parts = [{"name": "source_id", "value": "PF3D7_0100100"}]
        pk_refs = ["source_id", "project_id"]
        result = order_primary_key(
            pk_parts, pk_refs, pk_defaults={"project_id": "PlasmoDB"}
        )
        assert result == [
            {"name": "source_id", "value": "PF3D7_0100100"},
            {"name": "project_id", "value": "PlasmoDB"},
        ]

    def test_already_ordered(self):
        """PK parts already in correct order are unchanged."""
        pk_parts = [
            {"name": "source_id", "value": "PF3D7_0100100"},
            {"name": "project_id", "value": "PlasmoDB"},
        ]
        pk_refs = ["source_id", "project_id"]
        result = order_primary_key(pk_parts, pk_refs, pk_defaults={})
        assert result == pk_parts

    def test_empty_refs_returns_empty(self):
        """Empty primaryKeyColumnRefs returns empty list."""
        pk_parts = [{"name": "source_id", "value": "PF3D7_0100100"}]
        result = order_primary_key(pk_parts, [], pk_defaults={})
        assert result == []

    def test_extra_pk_parts_ignored(self):
        """PK parts not in refs are discarded."""
        pk_parts = [
            {"name": "source_id", "value": "PF3D7_0100100"},
            {"name": "project_id", "value": "PlasmoDB"},
            {"name": "extra_col", "value": "junk"},
        ]
        pk_refs = ["source_id", "project_id"]
        result = order_primary_key(pk_parts, pk_refs, pk_defaults={})
        assert len(result) == 2
        assert result[0]["name"] == "source_id"
        assert result[1]["name"] == "project_id"

    def test_missing_part_with_no_default_gets_empty_string(self):
        """Missing PK column with no default gets empty string value."""
        pk_parts = [{"name": "source_id", "value": "PF3D7_0100100"}]
        pk_refs = ["source_id", "project_id"]
        result = order_primary_key(pk_parts, pk_refs, pk_defaults={})
        assert result[1] == {"name": "project_id", "value": ""}
