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
