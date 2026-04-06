"""VEuPathDB WDK REST API client — composed from mixins.

Import the client from here:

    from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient

The class inherits:
- :class:`HTTPClient` — session management, retry logic, ``get``/``post``/``put``/etc.
- :class:`SearchEndpoints` — record-type and search endpoints
- :class:`AnalysisEndpoints` — analysis, step-filter, and report endpoints
"""

from veupath_chatbot.integrations.veupathdb._analyses import AnalysisEndpoints
from veupath_chatbot.integrations.veupathdb._http import HTTPClient
from veupath_chatbot.integrations.veupathdb._searches import SearchEndpoints


class VEuPathDBClient(HTTPClient, SearchEndpoints, AnalysisEndpoints):
    """HTTP client for VEuPathDB WDK REST services.

    Composed from :class:`HTTPClient` (transport), :class:`SearchEndpoints`
    (search/record-type methods), and :class:`AnalysisEndpoints`
    (analysis/filter/report methods).
    """
