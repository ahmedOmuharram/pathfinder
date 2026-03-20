"""Tests for services.gene_lookup.wdk -- WDK gene search and ID resolution."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from veupath_chatbot.services.gene_lookup.wdk import (
    WDK_TEXT_FIELDS_BROAD,
    WDK_TEXT_FIELDS_ID,
    WDK_WILDCARD_LIMIT,
    WdkTextResult,
    _parse_wdk_record,
    fetch_wdk_text_genes,
    resolve_gene_ids,
)

# ---------------------------------------------------------------------------
# _parse_wdk_record
# ---------------------------------------------------------------------------


class TestParseWdkRecord:
    """Tests for parsing a single WDK record into a gene result dict."""

    def _make_record(
        self,
        *,
        gene_source_id: str = "PF3D7_0100100",
        primary_key: str = "PF3D7_0100100",
        gene_name: str = "EMP1",
        gene_product: str = "erythrocyte membrane protein",
        organism: str = "Plasmodium falciparum 3D7",
        gene_type: str = "protein coding",
        gene_location_text: str = "Pf3D7_01_v3:100-200(+)",
        gene_previous_ids: str = "",
        pk_list: list[dict[str, str]] | None = None,
    ) -> dict[str, object]:
        rec: dict[str, object] = {
            "attributes": {
                "primary_key": primary_key,
                "gene_source_id": gene_source_id,
                "gene_name": gene_name,
                "gene_product": gene_product,
                "organism": organism,
                "gene_type": gene_type,
                "gene_location_text": gene_location_text,
                "gene_previous_ids": gene_previous_ids,
            },
        }
        if pk_list is not None:
            rec["id"] = pk_list
        return rec

    def test_basic_parsing(self) -> None:
        rec = self._make_record()
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["geneId"] == "PF3D7_0100100"
        assert result["geneName"] == "EMP1"
        assert result["product"] == "erythrocyte membrane protein"
        assert result["organism"] == "Plasmodium falciparum 3D7"
        assert result["geneType"] == "protein coding"
        assert result["location"] == "Pf3D7_01_v3:100-200(+)"

    def test_gene_id_from_pk_list(self) -> None:
        rec = self._make_record(
            gene_source_id="",
            primary_key="",
            pk_list=[
                {"name": "gene_source_id", "value": "PF3D7_FROM_PK"},
            ],
        )
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["geneId"] == "PF3D7_FROM_PK"

    def test_gene_id_from_source_id_name(self) -> None:
        rec = self._make_record(
            gene_source_id="",
            primary_key="",
            pk_list=[
                {"name": "source_id", "value": "PF3D7_SOURCE"},
            ],
        )
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["geneId"] == "PF3D7_SOURCE"

    def test_gene_id_from_gene_name_in_pk(self) -> None:
        rec = self._make_record(
            gene_source_id="",
            primary_key="",
            pk_list=[
                {"name": "gene", "value": "PF3D7_GENE"},
            ],
        )
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["geneId"] == "PF3D7_GENE"

    def test_gene_source_id_takes_priority(self) -> None:
        """gene_source_id attribute is used as geneId over primary_key."""
        rec = self._make_record(
            gene_source_id="SRC_ID",
            primary_key="PK_ID",
        )
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["geneId"] == "SRC_ID"

    def test_fallback_to_primary_key_attribute(self) -> None:
        rec = self._make_record(gene_source_id="", primary_key="PK_FALLBACK")
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["geneId"] == "PK_FALLBACK"

    def test_html_tags_stripped(self) -> None:
        rec = self._make_record(
            gene_name="<em>EMP1</em>",
            gene_product="<b>erythrocyte</b> membrane protein",
        )
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["geneName"] == "EMP1"
        assert result["product"] == "erythrocyte membrane protein"

    def test_empty_gene_name_treated_as_empty(self) -> None:
        rec = self._make_record(gene_name="")
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["geneName"] == ""

    def test_display_name_prefers_gene_name(self) -> None:
        rec = self._make_record(gene_name="MyGene", gene_product="MyProduct")
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["displayName"] == "MyGene"

    def test_display_name_falls_back_to_product(self) -> None:
        rec = self._make_record(gene_name="", gene_product="MyProduct")
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["displayName"] == "MyProduct"

    def test_display_name_falls_back_to_gene_id(self) -> None:
        rec = self._make_record(gene_name="", gene_product="")
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["displayName"] == "PF3D7_0100100"

    def test_previous_ids_set(self) -> None:
        rec = self._make_record(gene_previous_ids="OLD1, OLD2")
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["previousIds"] == "OLD1, OLD2"

    def test_missing_attributes_uses_empty_dict(self) -> None:
        rec: dict[str, object] = {"id": [{"name": "gene_source_id", "value": "GENE_X"}]}
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["geneId"] == "GENE_X"

    def test_non_dict_pk_elements_skipped(self) -> None:
        rec: dict[str, object] = {
            "id": ["not a dict", {"name": "gene_source_id", "value": "GENE_X"}],
            "attributes": {"gene_source_id": ""},
        }
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["geneId"] == "GENE_X"

    def test_pk_element_with_empty_value_skipped(self) -> None:
        rec: dict[str, object] = {
            "id": [{"name": "gene_source_id", "value": "  "}],
            "attributes": {"primary_key": "FALLBACK_PK"},
        }
        result = _parse_wdk_record(rec)
        assert result is not None
        assert result["geneId"] == "FALLBACK_PK"


# ---------------------------------------------------------------------------
# fetch_wdk_text_genes
# ---------------------------------------------------------------------------


class TestFetchWdkTextGenes:
    """Tests for the WDK GenesByText search."""

    def _mock_client(self, responses: list[dict[str, object]]) -> AsyncMock:
        client = AsyncMock()
        client.post = AsyncMock(side_effect=responses)
        return client

    @patch("veupath_chatbot.services.gene_lookup.wdk.get_wdk_client")
    async def test_empty_expressions_returns_empty(
        self, mock_get_client: MagicMock
    ) -> None:
        result = await fetch_wdk_text_genes("plasmodb", [], organism="Pf")
        assert result == WdkTextResult(records=[], total_count=0)
        mock_get_client.assert_not_called()

    @patch("veupath_chatbot.services.gene_lookup.wdk.get_wdk_client")
    async def test_no_organism_returns_empty(self, mock_get_client: MagicMock) -> None:
        result = await fetch_wdk_text_genes("plasmodb", ["kinase"], organism=None)
        assert result == WdkTextResult(records=[], total_count=0)
        mock_get_client.assert_not_called()

    @patch("veupath_chatbot.services.gene_lookup.wdk.get_wdk_client")
    async def test_single_expression_returns_records(
        self, mock_get_client: MagicMock
    ) -> None:
        mock_client = self._mock_client(
            [
                {
                    "meta": {"totalCount": 1},
                    "records": [
                        {
                            "id": [
                                {"name": "gene_source_id", "value": "PF3D7_0100100"}
                            ],
                            "attributes": {
                                "gene_source_id": "PF3D7_0100100",
                                "primary_key": "PF3D7_0100100",
                                "gene_name": "EMP1",
                                "gene_product": "erythrocyte membrane protein",
                                "organism": "Plasmodium falciparum 3D7",
                                "gene_type": "protein coding",
                                "gene_location_text": "chr1:100-200(+)",
                                "gene_previous_ids": "",
                            },
                        }
                    ],
                }
            ]
        )
        mock_get_client.return_value = mock_client

        result = await fetch_wdk_text_genes(
            "plasmodb",
            ["kinase*"],
            organism="Plasmodium falciparum 3D7",
            text_fields=WDK_TEXT_FIELDS_ID,
        )
        assert len(result.records) == 1
        assert result.records[0]["geneId"] == "PF3D7_0100100"
        assert result.total_count == 1

    @patch("veupath_chatbot.services.gene_lookup.wdk.get_wdk_client")
    async def test_multiple_expressions_iterated(
        self, mock_get_client: MagicMock
    ) -> None:
        mock_client = self._mock_client(
            [
                {
                    "meta": {"totalCount": 1},
                    "records": [
                        {
                            "attributes": {
                                "gene_source_id": "GENE_A",
                                "primary_key": "GENE_A",
                                "gene_name": "",
                                "gene_product": "prod A",
                                "organism": "Pf",
                                "gene_type": "",
                                "gene_location_text": "",
                                "gene_previous_ids": "",
                            },
                        }
                    ],
                },
                {
                    "meta": {"totalCount": 2},
                    "records": [
                        {
                            "attributes": {
                                "gene_source_id": "GENE_B",
                                "primary_key": "GENE_B",
                                "gene_name": "",
                                "gene_product": "prod B",
                                "organism": "Pf",
                                "gene_type": "",
                                "gene_location_text": "",
                                "gene_previous_ids": "",
                            },
                        }
                    ],
                },
            ]
        )
        mock_get_client.return_value = mock_client

        result = await fetch_wdk_text_genes(
            "plasmodb",
            ["expr1", "expr2"],
            organism="Pf",
            limit=100,
        )
        assert len(result.records) == 2
        assert result.total_count == 2  # max of wdk_total (2) vs len(records) (2)
        assert mock_client.post.call_count == 2

    @patch("veupath_chatbot.services.gene_lookup.wdk.get_wdk_client")
    async def test_limit_stops_iteration(self, mock_get_client: MagicMock) -> None:
        """When we reach the limit, stop iterating expressions."""
        records = [
            {
                "attributes": {
                    "gene_source_id": f"GENE_{i}",
                    "primary_key": f"GENE_{i}",
                    "gene_name": "",
                    "gene_product": f"product {i}",
                    "organism": "Pf",
                    "gene_type": "",
                    "gene_location_text": "",
                    "gene_previous_ids": "",
                },
            }
            for i in range(5)
        ]
        mock_client = self._mock_client(
            [
                {"meta": {"totalCount": 100}, "records": records},
                {
                    "meta": {"totalCount": 50},
                    "records": records,
                },  # Should not be called
            ]
        )
        mock_get_client.return_value = mock_client

        result = await fetch_wdk_text_genes(
            "plasmodb",
            ["expr1", "expr2"],
            organism="Pf",
            limit=3,
        )
        assert len(result.records) == 3
        assert (
            mock_client.post.call_count == 1
        )  # Stopped after first expression hit limit

    @patch("veupath_chatbot.services.gene_lookup.wdk.get_wdk_client")
    async def test_non_dict_answer_skipped(self, mock_get_client: MagicMock) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value="not a dict")
        mock_get_client.return_value = mock_client

        result = await fetch_wdk_text_genes(
            "plasmodb",
            ["kinase*"],
            organism="Pf",
        )
        assert result.records == []
        assert result.total_count == 0

    @patch("veupath_chatbot.services.gene_lookup.wdk.get_wdk_client")
    async def test_non_list_records_skipped(self, mock_get_client: MagicMock) -> None:
        mock_client = self._mock_client(
            [
                {"meta": {"totalCount": 5}, "records": "not a list"},
            ]
        )
        mock_get_client.return_value = mock_client

        result = await fetch_wdk_text_genes(
            "plasmodb",
            ["kinase*"],
            organism="Pf",
        )
        assert result.records == []
        assert result.total_count == 5

    @patch("veupath_chatbot.services.gene_lookup.wdk.get_wdk_client")
    async def test_non_dict_record_entries_skipped(
        self, mock_get_client: MagicMock
    ) -> None:
        mock_client = self._mock_client(
            [
                {
                    "meta": {"totalCount": 2},
                    "records": [
                        "not a dict",
                        {
                            "attributes": {
                                "gene_source_id": "GENE_OK",
                                "primary_key": "GENE_OK",
                                "gene_name": "",
                                "gene_product": "",
                                "organism": "",
                                "gene_type": "",
                                "gene_location_text": "",
                                "gene_previous_ids": "",
                            },
                        },
                    ],
                },
            ]
        )
        mock_get_client.return_value = mock_client

        result = await fetch_wdk_text_genes(
            "plasmodb",
            ["kinase*"],
            organism="Pf",
        )
        assert len(result.records) == 1
        assert result.records[0]["geneId"] == "GENE_OK"

    @patch("veupath_chatbot.services.gene_lookup.wdk.get_wdk_client")
    async def test_default_text_fields_used(self, mock_get_client: MagicMock) -> None:
        """When text_fields is None, defaults to WDK_TEXT_FIELDS_ID."""
        mock_client = self._mock_client(
            [
                {"meta": {"totalCount": 0}, "records": []},
            ]
        )
        mock_get_client.return_value = mock_client

        await fetch_wdk_text_genes(
            "plasmodb",
            ["test*"],
            organism="Pf",
            text_fields=None,
        )

        call_json = mock_client.post.call_args[1]["json"]
        sent_fields = json.loads(call_json["searchConfig"]["parameters"]["text_fields"])
        assert sent_fields == WDK_TEXT_FIELDS_ID

    @patch("veupath_chatbot.services.gene_lookup.wdk.get_wdk_client")
    async def test_meta_totalcount_non_int_ignored(
        self, mock_get_client: MagicMock
    ) -> None:
        mock_client = self._mock_client(
            [
                {"meta": {"totalCount": "not_int"}, "records": []},
            ]
        )
        mock_get_client.return_value = mock_client

        result = await fetch_wdk_text_genes(
            "plasmodb",
            ["kinase*"],
            organism="Pf",
        )
        assert result.total_count == 0

    @patch("veupath_chatbot.services.gene_lookup.wdk.get_wdk_client")
    async def test_meta_missing_treated_gracefully(
        self, mock_get_client: MagicMock
    ) -> None:
        mock_client = self._mock_client(
            [
                {"records": []},
            ]
        )
        mock_get_client.return_value = mock_client

        result = await fetch_wdk_text_genes(
            "plasmodb",
            ["kinase*"],
            organism="Pf",
        )
        assert result.total_count == 0


# ---------------------------------------------------------------------------
# resolve_gene_ids
# ---------------------------------------------------------------------------


class TestResolveGeneIds:
    """Tests for the WDK gene ID resolution."""

    async def test_empty_ids_returns_empty(self) -> None:
        result = await resolve_gene_ids("plasmodb", [])
        assert result == {"records": [], "totalCount": 0}


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestWdkConstants:
    def test_wildcard_limit(self) -> None:
        assert WDK_WILDCARD_LIMIT == 50

    def test_text_fields_id_contains_primary_key(self) -> None:
        assert "primary_key" in WDK_TEXT_FIELDS_ID

    def test_text_fields_id_contains_alias(self) -> None:
        assert "Alias" in WDK_TEXT_FIELDS_ID

    def test_text_fields_broad_superset_of_id(self) -> None:
        for field in WDK_TEXT_FIELDS_ID:
            assert field in WDK_TEXT_FIELDS_BROAD

    def test_text_fields_broad_contains_product(self) -> None:
        assert "product" in WDK_TEXT_FIELDS_BROAD

    def test_text_fields_broad_contains_goterms(self) -> None:
        assert "GOTerms" in WDK_TEXT_FIELDS_BROAD
