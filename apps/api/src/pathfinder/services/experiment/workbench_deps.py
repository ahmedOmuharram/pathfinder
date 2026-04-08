"""Typed dependency injection for workbench chat pydantic-ai tools.

``WorkbenchDeps`` is passed to every workbench tool via
``RunContext[WorkbenchDeps]``.  It provides the site, experiment, and
user context that the analysis/refinement tools need.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass
class WorkbenchDeps:
    """Shared dependencies for workbench chat tools."""

    site_id: str
    experiment_id: str
    user_id: UUID | None = None
