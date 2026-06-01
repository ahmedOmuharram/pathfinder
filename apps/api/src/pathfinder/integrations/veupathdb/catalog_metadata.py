"""Catalog metadata helpers: dataset summaries, ontology categories, record type processing."""

from pydantic import ConfigDict, Field

from pathfinder.integrations.veupathdb.client import VEuPathDBClient
from pathfinder.integrations.veupathdb.disk_cache import DatasetReport
from pathfinder.integrations.veupathdb.wdk_models import WDKRecordType, WDKSearch
from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.pydantic_base import CamelModel

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Dataset metadata
# ---------------------------------------------------------------------------


class DatasetMetadata:
    """Result of loading dataset summaries and contacts."""

    __slots__ = ("contacts", "summaries")

    def __init__(
        self,
        summaries: dict[str, str],
        contacts: dict[str, str],
    ) -> None:
        self.summaries = summaries
        self.contacts = contacts


async def load_dataset_metadata(
    client: VEuPathDBClient, site_id: str
) -> DatasetMetadata:
    """Fetch all dataset summaries and contacts in one call.

    Returns empty metadata on failure (non-fatal).
    """
    summaries: dict[str, str] = {}
    contacts: dict[str, str] = {}
    try:
        report_config = {
            "attributes": ["primary_key", "summary", "contact"],
        }
        answer = await client.post(
            "/record-types/dataset/searches/AllDatasets/reports/standard",
            json={"searchConfig": {"parameters": {}}, "reportConfig": report_config},
        )
        report = DatasetReport.model_validate(answer)
        for rec in report.records:
            rec.populate(summaries, contacts)
        logger.info(
            "Dataset metadata loaded",
            site_id=site_id,
            datasets=len(summaries),
        )
    except AppError, OSError, ValueError, TypeError:
        logger.warning(
            "Failed to load dataset metadata (non-fatal)",
            site_id=site_id,
            exc_info=True,
        )
    return DatasetMetadata(summaries=summaries, contacts=contacts)


# ---------------------------------------------------------------------------
# Ontology categories
# ---------------------------------------------------------------------------


class OntologyCategories:
    """Result of loading ontology category mappings."""

    __slots__ = ("available_categories", "search_categories", "search_category_labels")

    def __init__(
        self,
        search_categories: dict[str, str],
        available_categories: set[str],
        search_category_labels: dict[str, str],
    ) -> None:
        self.search_categories = search_categories
        self.available_categories = available_categories
        self.search_category_labels = search_category_labels


class _OntologyNodeProps(CamelModel):
    """Properties bag on a Categories ontology node."""

    model_config = ConfigDict(extra="ignore")

    label: list[str] = Field(default_factory=list)
    eu_path_db_alternative_term: list[str] = Field(
        default_factory=list,
        alias="EuPathDB alternative term",
    )

    @property
    def label_str(self) -> str:
        return str(self.label[0]) if self.label else ""

    @property
    def display_name(self) -> str:
        if self.eu_path_db_alternative_term:
            return str(self.eu_path_db_alternative_term[0])
        return self.label_str


class _OntologyNode(CamelModel):
    """Minimal parse of a Categories ontology tree node."""

    model_config = ConfigDict(extra="ignore")

    properties: _OntologyNodeProps = Field(default_factory=_OntologyNodeProps)
    children: list[_OntologyNode] = Field(default_factory=list)


class _OntologyResponse(CamelModel):
    """Top-level response from /ontologies/Categories."""

    model_config = ConfigDict(extra="ignore")

    tree: _OntologyNode = Field(default_factory=_OntologyNode)


async def load_ontology_categories(
    client: VEuPathDBClient, site_id: str
) -> OntologyCategories:
    """Fetch the Categories ontology and map searches to subcategories.

    Also extracts top-level human-readable category labels for semantic
    index enrichment (e.g. "Protein features and properties").

    Returns empty mappings on failure (non-fatal).
    """
    search_categories: dict[str, str] = {}
    search_category_labels: dict[str, str] = {}
    available_categories: set[str] = set()

    try:
        data = await client.get("/ontologies/Categories")
        response = _OntologyResponse.model_validate(data)
        tree = response.tree

        def walk(
            node: _OntologyNode,
            ancestors: list[str],
            ancestor_display_names: list[str],
        ) -> None:
            label = node.properties.label_str
            display_name = node.properties.display_name

            if not node.children and "GeneQuestions" in label:
                search_name = label.split(".")[-1]
                for ancestor in reversed(ancestors):
                    if ancestor.startswith("searchCategory-"):
                        search_categories[search_name] = ancestor
                        available_categories.add(ancestor)
                        break
                for anc_display in reversed(ancestor_display_names):
                    if anc_display and not anc_display.startswith("searchCategory-"):
                        search_category_labels[search_name] = anc_display
                        break

            for child in node.children:
                walk(
                    child, [*ancestors, label], [*ancestor_display_names, display_name]
                )

        walk(tree, [], [])
        logger.info(
            "Ontology categories loaded",
            site_id=site_id,
            categorized_searches=len(search_categories),
            categories=len(available_categories),
            labeled_searches=len(search_category_labels),
        )
    except AppError, OSError, ValueError, TypeError:
        logger.warning(
            "Failed to load ontology categories (non-fatal)",
            site_id=site_id,
            exc_info=True,
        )
    return OntologyCategories(
        search_categories=search_categories,
        available_categories=available_categories,
        search_category_labels=search_category_labels,
    )


# ---------------------------------------------------------------------------
# Record type processing helpers
# ---------------------------------------------------------------------------


async def load_searches_for_rt(
    client: VEuPathDBClient, rt_name: str
) -> list[WDKSearch] | None:
    """Fetch searches for a record type, returning None on error."""
    try:
        return await client.get_searches(rt_name)
    except AppError as e:
        logger.warning(
            "Failed to load searches",
            record_type=rt_name,
            error=str(e),
        )
        return None


def process_record_type_entry(
    rt: WDKRecordType,
    *,
    expanded_supported: bool,
) -> tuple[WDKRecordType, list[WDKSearch] | None] | None:
    """Extract (typed_rt, inline_searches) from a record type entry.

    Returns None if the entry should be skipped. Returns (model, None) when
    searches need to be fetched separately.
    """
    if not rt.url_segment:
        return None

    if expanded_supported and rt.searches is not None:
        return rt, rt.searches
    return rt, None
