"""Shared helper for building combined RAG + WDK tool outputs."""

from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONObject, JSONValue


class DataSourceEntry(CamelModel):
    """A single data-source entry in a combined RAG+WDK response."""

    data: JSONValue = None
    note: str = ""


class CombinedResultResponse(CamelModel):
    """Typed combined RAG + WDK response for AI tools."""

    rag: DataSourceEntry
    wdk: DataSourceEntry


def combined_result(
    *,
    rag: JSONValue,
    wdk: JSONValue,
    rag_note: str | None = None,
    wdk_note: str | None = None,
) -> JSONObject:
    """Standardize combined (RAG + WDK) tool outputs.

    Callers always receive both data sources and can decide which to trust
    based on availability/staleness.

    :param rag: RAG context.
    :param wdk: WDK context.
    :param rag_note: RAG note (default: None).
    :param wdk_note: WDK note (default: None).
    """
    return CombinedResultResponse(
        rag=DataSourceEntry(data=rag, note=rag_note or ""),
        wdk=DataSourceEntry(data=wdk, note=wdk_note or ""),
    ).model_dump(by_alias=True, mode="json")
