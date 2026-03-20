"""Shared fake objects for unit tests.

Consolidates fake/stub classes that were duplicated across 3+ test files.
Import from here instead of redefining in each test module.
"""


class FakeResultToolsSession:
    """Minimal fake session for ResultTools tests.

    Used in test_result_tools.py, test_execution_tools_get_sample_records.py,
    and test_execution_tools_get_download_url.py.
    """

    def __init__(self, site_id: str = "plasmodb") -> None:
        self.site_id = site_id

    def get_graph(self, graph_id: str | None):
        del graph_id


class FakeStrategyAPI:
    """Fake strategy API that returns a canned response or raises an error.

    Used by ResultTools tests for get_step_answer.
    """

    def __init__(self, response=None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error

    async def get_step_answer(
        self, step_id: int, pagination: dict[str, int] | None = None
    ):
        del step_id
        del pagination
        if self._error is not None:
            raise self._error
        return self._response


class FakeResultsAPI:
    """Fake results API that returns a canned URL or raises an error.

    Used by ResultTools tests for get_download_url.
    """

    def __init__(self, url: str | None = None, error: Exception | None = None) -> None:
        self._url = url
        self._error = error

    async def get_download_url(
        self,
        step_id: int,
        output_format: str = "csv",
        attributes: list[str] | None = None,
    ) -> str:
        del step_id
        del output_format
        del attributes
        if self._error is not None:
            raise self._error
        return self._url or ""
