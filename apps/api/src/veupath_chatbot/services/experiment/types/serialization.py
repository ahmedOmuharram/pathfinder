"""JSON serialization for experiment types.

Now that all experiment types are Pydantic models, serialization is handled
by ``model_dump(by_alias=True)``.  These thin wrappers exist to preserve the
call-site API and add the summary projection logic.
"""

from typing import cast

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.types.experiment import Experiment


def experiment_to_json(exp: Experiment) -> JSONObject:
    """Serialize a full :class:`Experiment` to a camelCase JSON dict."""
    return cast("JSONObject", exp.model_dump(by_alias=True))


def experiment_summary_to_json(exp: Experiment) -> JSONObject:
    """Serialize an experiment to a lightweight summary dict."""
    return {
        "id": exp.id,
        "name": exp.config.name,
        "siteId": exp.config.site_id,
        "searchName": exp.config.search_name,
        "recordType": exp.config.record_type,
        "mode": exp.config.mode,
        "status": exp.status,
        "f1Score": round(exp.metrics.f1_score, 4) if exp.metrics else None,
        "sensitivity": round(exp.metrics.sensitivity, 4) if exp.metrics else None,
        "specificity": round(exp.metrics.specificity, 4) if exp.metrics else None,
        "totalPositives": len(exp.config.positive_controls),
        "totalNegatives": len(exp.config.negative_controls),
        "createdAt": exp.created_at,
        "batchId": exp.batch_id,
        "benchmarkId": exp.benchmark_id,
        "controlSetLabel": exp.control_set_label,
        "isPrimaryBenchmark": exp.is_primary_benchmark,
    }
