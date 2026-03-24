"""Export service — CSV/TSV/TXT generation + Redis temp storage."""

import base64
import csv
import io
import json
import re
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel
from redis.asyncio import Redis

from veupath_chatbot.platform.context import request_base_url_ctx
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.enrichment.types import EnrichmentResult
from veupath_chatbot.services.experiment.types import Experiment
from veupath_chatbot.services.gene_sets.types import GeneSet

logger = get_logger(__name__)

EXPORT_TTL = 600  # 10 minutes
REDIS_PREFIX = "export:"


class _ExportPayload(BaseModel):
    """Shape of the JSON blob stored in Redis for each export."""

    filename: str
    content_type: str
    data: str  # base64-encoded content bytes


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Metadata returned after generating an export file."""

    export_id: str
    filename: str
    content_type: str
    url: str
    size_bytes: int
    expires_in_seconds: int


def _sanitize_filename(name: str) -> str:
    """Strip non-alphanumeric chars from a name for use in filenames."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:60]


class ExportService:
    """Generates downloadable files and stores them in Redis with TTL."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def _store(
        self, content: bytes, filename: str, content_type: str
    ) -> ExportResult:
        """Store file bytes in Redis and return export metadata."""
        export_id = str(uuid4())
        key = f"{REDIS_PREFIX}{export_id}"
        payload = _ExportPayload(
            filename=filename,
            content_type=content_type,
            data=base64.b64encode(content).decode("ascii"),
        )
        await self._redis.set(
            key, payload.model_dump_json().encode("utf-8"), ex=EXPORT_TTL
        )
        logger.info(
            "Export stored",
            export_id=export_id,
            filename=filename,
            size_bytes=len(content),
        )
        base = request_base_url_ctx.get() or ""
        return ExportResult(
            export_id=export_id,
            filename=filename,
            content_type=content_type,
            url=f"{base}/api/v1/exports/{export_id}",
            size_bytes=len(content),
            expires_in_seconds=EXPORT_TTL,
        )

    async def get_export(self, export_id: str) -> tuple[bytes, str, str] | None:
        """Retrieve stored export. Returns (content, filename, content_type) or None."""
        key = f"{REDIS_PREFIX}{export_id}"
        raw = await self._redis.get(key)
        if raw is None:
            return None
        payload = _ExportPayload.model_validate_json(raw)
        content = base64.b64decode(payload.data)
        return content, payload.filename, payload.content_type

    async def export_gene_set(
        self, gene_set: GeneSet, output_format: Literal["csv", "txt"]
    ) -> ExportResult:
        """Export a gene set as CSV or TXT."""
        name_part = _sanitize_filename(gene_set.name or "gene_set")
        if output_format == "txt":
            content = "\n".join(gene_set.gene_ids).encode("utf-8")
            return await self._store(content, f"{name_part}.txt", "text/plain")
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["gene_id"])
        for gid in gene_set.gene_ids:
            writer.writerow([gid])
        return await self._store(
            buf.getvalue().encode("utf-8"), f"{name_part}.csv", "text/csv"
        )

    def _enrichment_rows(
        self, results: list[EnrichmentResult]
    ) -> tuple[list[str], list[list[object]]]:
        """Build header + data rows from enrichment results."""
        header = [
            "analysis_type",
            "term_id",
            "term_name",
            "gene_count",
            "background_count",
            "fold_enrichment",
            "odds_ratio",
            "p_value",
            "fdr",
            "bonferroni",
            "genes",
        ]
        rows: list[list[object]] = [
            [
                result.analysis_type,
                term.term_id,
                term.term_name,
                term.gene_count,
                term.background_count,
                term.fold_enrichment,
                term.odds_ratio,
                term.p_value,
                term.fdr,
                term.bonferroni,
                ";".join(term.genes),
            ]
            for result in results
            for term in result.terms
        ]
        return header, rows

    async def export_enrichment(
        self, results: list[EnrichmentResult], name: str
    ) -> ExportResult:
        """Export enrichment results as CSV."""
        name_part = _sanitize_filename(name or "enrichment")
        header, rows = self._enrichment_rows(results)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)
        return await self._store(
            buf.getvalue().encode("utf-8"), f"{name_part}_enrichment.csv", "text/csv"
        )

    async def export_enrichment_tsv(
        self, results: list[EnrichmentResult], name: str
    ) -> ExportResult:
        """Export enrichment results as TSV."""
        name_part = _sanitize_filename(name or "enrichment")
        header, rows = self._enrichment_rows(results)
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter="\t")
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)
        return await self._store(
            buf.getvalue().encode("utf-8"),
            f"{name_part}_enrichment.tsv",
            "text/tab-separated-values",
        )

    async def export_enrichment_json(
        self, results: list[EnrichmentResult], name: str
    ) -> ExportResult:
        """Export enrichment results as JSON."""
        name_part = _sanitize_filename(name or "enrichment")
        serialized = [r.model_dump(by_alias=True) for r in results]
        content = json.dumps(serialized, indent=2).encode("utf-8")
        return await self._store(
            content, f"{name_part}_enrichment.json", "application/json"
        )

    async def export_json(self, data: object, name: str) -> ExportResult:
        """Export arbitrary data as JSON."""
        name_part = _sanitize_filename(name or "export")
        content = json.dumps(data, indent=2, default=str).encode("utf-8")
        return await self._store(content, f"{name_part}.json", "application/json")

    async def export_experiment_results(
        self, experiment: Experiment, output_format: Literal["csv", "tsv"]
    ) -> ExportResult:
        """Export experiment gene classifications as CSV or TSV."""
        name_part = _sanitize_filename(experiment.config.name or experiment.id)
        delimiter = "\t" if output_format == "tsv" else ","
        ext = "tsv" if output_format == "tsv" else "csv"
        content_type = (
            "text/tab-separated-values" if output_format == "tsv" else "text/csv"
        )

        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=delimiter)
        writer.writerow(
            ["gene_id", "gene_name", "organism", "product", "classification"]
        )

        for label, genes in [
            ("TP", experiment.true_positive_genes),
            ("FP", experiment.false_positive_genes),
            ("FN", experiment.false_negative_genes),
            ("TN", experiment.true_negative_genes),
        ]:
            for gene in genes:
                writer.writerow(
                    [
                        gene.id,
                        gene.name or "",
                        gene.organism or "",
                        gene.product or "",
                        label,
                    ]
                )

        return await self._store(
            buf.getvalue().encode("utf-8"), f"{name_part}_results.{ext}", content_type
        )
