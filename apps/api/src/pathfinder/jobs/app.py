from __future__ import annotations

import procrastinate

from pathfinder.ai.conversation.checkpointer import to_psycopg_url
from pathfinder.platform.config import get_settings


def _build_connector() -> procrastinate.PsycopgConnector:
    """Build a PsycopgConnector pointing at the app's Postgres database."""
    return procrastinate.PsycopgConnector(
        conninfo=to_psycopg_url(get_settings().database_url),
    )


procrastinate_app: procrastinate.App = procrastinate.App(
    connector=_build_connector(),
)
