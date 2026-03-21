"""Deserialize JSON dicts back into Experiment model trees.

Now that all experiment types are Pydantic models, deserialization is handled
by ``Model.model_validate(data)``.  This module provides a thin wrapper that
handles the enrichment deduplication logic.
"""

from typing import Any

from veupath_chatbot.services.experiment.types.experiment import Experiment


def experiment_from_json(d: dict[str, Any]) -> Experiment:
    """Reconstruct an :class:`Experiment` from its JSON representation.

    :param d: Dict produced by :func:`experiment_to_json`.
    :returns: Fully hydrated Experiment instance.
    """
    # Deduplicate enrichment results by analysis_type, keeping the last
    # (most recent) entry.  This cleans up data persisted before the
    # upsert_enrichment_result helper was introduced.
    raw_er = d.get("enrichmentResults")
    if raw_er and isinstance(raw_er, list):
        seen: dict[str, int] = {}
        for i, er in enumerate(raw_er):
            key = er.get("analysisType", "") if isinstance(er, dict) else ""
            seen[key] = i
        d["enrichmentResults"] = [raw_er[i] for i in sorted(seen.values())]

    return Experiment.model_validate(d)
