"""Typed models for catalog service responses.

These are lightweight service-layer models used by ``sites.py`` to return
structured data to transport handlers.  They are NOT WDK integration models
(those live in ``integrations.veupathdb.wdk_models``).
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecordTypeInfo:
    """Simplified record type summary for API responses.

    Contains only the fields needed by transport handlers — the full
    WDK record type (with searches, properties, etc.) stays in the
    integration layer as ``WDKRecordType``.
    """

    name: str
    display_name: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class SearchMatch:
    """A search result from search_for_searches.

    Replaces the untyped ``dict[str, str]`` that was previously threaded
    through scoring, site-search bonus, and final results.
    """

    name: str
    display_name: str
    description: str
    record_type: str
    category: str = ""
    returns: str = ""

    def to_dict(self) -> dict[str, str]:
        """Serialize to the camelCase dict shape expected by AI tool callers."""
        result: dict[str, str] = {
            "name": self.name,
            "displayName": self.display_name,
            "description": self.description,
            "recordType": self.record_type,
        }
        if self.category:
            result["category"] = self.category
        if self.returns:
            result["returns"] = self.returns
        return result
