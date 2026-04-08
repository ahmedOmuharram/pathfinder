"""Catalog metadata helpers: dataset summaries, ontology categories, record type processing."""

from pathfinder.integrations.veupathdb.client import VEuPathDBClient
from pathfinder.integrations.veupathdb.disk_cache import DatasetReport
from pathfinder.integrations.veupathdb.wdk_models import WDKRecordType, WDKSearch
from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger

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
    except (AppError, OSError, ValueError, TypeError):
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

    __slots__ = ("available_categories", "search_categories")

    def __init__(
        self,
        search_categories: dict[str, str],
        available_categories: set[str],
    ) -> None:
        self.search_categories = search_categories
        self.available_categories = available_categories


async def load_ontology_categories(
    client: VEuPathDBClient, site_id: str
) -> OntologyCategories:
    """Fetch the Categories ontology and map searches to subcategories.

    Returns empty mappings on failure (non-fatal).
    """
    search_categories: dict[str, str] = {}
    available_categories: set[str] = set()

    try:
        data = await client.get("/ontologies/Categories")
        tree = data.get("tree", data) if isinstance(data, dict) else {}

        def walk(node: dict, ancestors: list[str]) -> None:
            props = node.get("properties", {})
            label_list = props.get("label", [""])
            label = str(label_list[0]) if label_list else ""
            children = node.get("children", [])

            if not children and "GeneQuestions" in label:
                for ancestor in reversed(ancestors):
                    if ancestor.startswith("searchCategory-"):
                        search_name = label.split(".")[-1]
                        search_categories[search_name] = ancestor
                        available_categories.add(ancestor)
                        break

            for child in children:
                if isinstance(child, dict):
                    walk(child, [*ancestors, label])

        walk(tree, [])
        logger.info(
            "Ontology categories loaded",
            site_id=site_id,
            categorized_searches=len(search_categories),
            categories=len(available_categories),
        )
    except (AppError, OSError, ValueError, TypeError):
        logger.warning(
            "Failed to load ontology categories (non-fatal)",
            site_id=site_id,
            exc_info=True,
        )
    return OntologyCategories(
        search_categories=search_categories,
        available_categories=available_categories,
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
