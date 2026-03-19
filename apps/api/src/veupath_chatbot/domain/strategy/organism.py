"""Organism scope extraction from strategy step trees."""

from collections.abc import Mapping

from veupath_chatbot.domain.parameters._decode_values import decode_values
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.platform.types import JSONValue

_ORGANISM_PARAMS = ("organism", "text_search_organism")


def _parse_organisms(params: Mapping[str, JSONValue]) -> set[str] | None:
    """Extract organism names from step parameters, or None if absent."""
    for key in _ORGANISM_PARAMS:
        raw = params.get(key)
        if raw is not None:
            vals = decode_values(raw, key)
            if vals:
                return {str(v) for v in vals}
    return None


def extract_output_organisms(step: PlanStepNode) -> set[str] | None:
    """Return the organism scope of a step's output, or None if unknown.

    GenesByOrthologs changes the scope to its target organism.
    Combines and other transforms inherit from their primary input.
    Leaf steps use their organism parameter directly.
    """
    # Ortholog transform defines its own output organism.
    if step.search_name == "GenesByOrthologs" and step.parameters:
        return _parse_organisms(step.parameters)

    # Any step with a primary input inherits from it.
    if step.primary_input is not None:
        return extract_output_organisms(step.primary_input)

    # Leaf: read organism directly.
    return _parse_organisms(step.parameters) if step.parameters else None
