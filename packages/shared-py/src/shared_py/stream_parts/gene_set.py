"""Typed payload for workbench_gene_set data-part."""

from __future__ import annotations

from pydantic import Field

from shared_py.pydantic_base import CamelModel


class GeneSet(CamelModel):
    gene_set_id: str
    name: str
    gene_count: int = Field(ge=0)
    site_id: str
