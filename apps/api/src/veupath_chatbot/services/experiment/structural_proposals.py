"""LLM-powered structural variant proposals for tree optimisation.

Calls an LLM to analyse the current strategy tree and propose structural
modifications (ortholog insertion, branch pruning, input swapping, step
addition/replacement) that Optuna can then select among during optimisation.
"""

from __future__ import annotations

import json
from typing import Any

from kani import Kani

from veupath_chatbot.ai.agents.factory import create_engine
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.tree_optimization import (
    StructuralEdit,
    StructuralVariant,
    TreeOptimizationConfig,
)
from veupath_chatbot.services.experiment.types import ExperimentMetrics

logger = get_logger(__name__)

_MODEL_ID = "openai/gpt-4o-mini"


def _serialise_tree_compact(tree: JSONObject, depth: int = 0) -> str:
    """Produce a human-readable indented summary of the strategy tree.

    :param tree: ``PlanStepNode``-shaped dict.
    :param depth: Current indentation depth.
    :returns: Multi-line string representation.
    """
    indent = "  " * depth
    node_id = tree.get("id", tree.get("searchName", "?"))
    search = tree.get("searchName", "")
    operator = tree.get("operator", "")
    params = tree.get("parameters", {})

    pi = tree.get("primaryInput")
    si = tree.get("secondaryInput")
    is_combine = isinstance(pi, dict) and isinstance(si, dict)
    is_transform = isinstance(pi, dict) and not isinstance(si, dict)

    if is_combine:
        kind = "COMBINE"
    elif is_transform:
        kind = "TRANSFORM"
    else:
        kind = "SEARCH"

    param_summary = ""
    if isinstance(params, dict) and params:
        items = [f"{k}={v}" for k, v in list(params.items())[:5]]
        param_summary = f"  params={{{', '.join(items)}}}"

    lines = [
        f"{indent}[{kind}] id={node_id}  search={search}  op={operator}{param_summary}"
    ]

    if isinstance(pi, dict):
        lines.append(_serialise_tree_compact(pi, depth + 1))
    if isinstance(si, dict):
        lines.append(_serialise_tree_compact(si, depth + 1))

    return "\n".join(lines)


def _build_system_prompt(
    tree_text: str,
    node_ids: list[str],
    searches_summary: str,
    organisms_summary: str,
    baseline_summary: str,
) -> str:
    """Build the system prompt for the structural analysis LLM call.

    :param tree_text: Human-readable tree representation.
    :param node_ids: All node IDs in the tree.
    :param searches_summary: Available searches.
    :param organisms_summary: Available ortholog organisms.
    :param baseline_summary: Baseline metrics summary.
    :returns: System prompt string.
    """
    return f"""\
You are a bioinformatics expert analysing a VEuPathDB search strategy tree.
Your job is to propose up to 5 structural modifications that could improve
the strategy's ability to correctly identify target genes (maximise balanced
accuracy / F1 against known positive and negative control genes).

STRATEGY TREE (indented, root at top):
{tree_text}

NODE IDS: {", ".join(node_ids)}

BASELINE METRICS:
{baseline_summary}

AVAILABLE SEARCHES for this record type (name — description):
{searches_summary}

AVAILABLE ORTHOLOG ORGANISMS:
{organisms_summary}

Each proposal is a named variant with one or more edits. Valid edit kinds:

1. ortholog_insert — Insert a GenesByOrthologs transform after a node.
   Fields: kind="ortholog_insert", target_node_id, organism
2. branch_prune — Remove one child branch of a combine node (keep the other).
   Fields: kind="branch_prune", target_node_id (the combine node)
3. input_swap — Swap primary/secondary inputs at a combine node.
   Fields: kind="input_swap", target_node_id
4. step_add — Add a new search step combined (INTERSECT) with a node.
   Fields: kind="step_add", target_node_id, search_name, parameters (dict), operator (optional, default INTERSECT)
5. step_replace — Replace a leaf search with a different one.
   Fields: kind="step_replace", target_node_id, search_name, parameters (dict)

Rules:
- target_node_id must be one of the listed NODE IDS.
- branch_prune only on COMBINE nodes.
- input_swap only on COMBINE nodes.
- step_replace only on SEARCH (leaf) nodes.
- Each variant should be a meaningful, biologically motivated change.
- Return ONLY valid JSON (no markdown fences).

Return a JSON array of variant objects:
[
  {{
    "name": "short description",
    "rationale": "biological reasoning",
    "edits": [
      {{"kind": "...", "target_node_id": "...", ...}}
    ]
  }}
]"""


def _collect_node_ids(tree: JSONObject) -> list[str]:
    """Recursively collect all node IDs from the tree.

    :param tree: ``PlanStepNode``-shaped dict.
    :returns: List of node ID strings.
    """
    ids: list[str] = []
    node_id = str(tree.get("id", tree.get("searchName", "")))
    if node_id:
        ids.append(node_id)
    pi = tree.get("primaryInput")
    si = tree.get("secondaryInput")
    if isinstance(pi, dict):
        ids.extend(_collect_node_ids(pi))
    if isinstance(si, dict):
        ids.extend(_collect_node_ids(si))
    return ids


def _parse_variants(raw: str) -> list[StructuralVariant]:
    """Parse LLM JSON response into validated ``StructuralVariant`` objects.

    :param raw: Raw JSON string from LLM.
    :returns: List of validated variants (invalid entries are dropped).
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end != -1:
            try:
                data = json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                logger.warning("Failed to parse structural proposals JSON")
                return []
        else:
            return []

    if not isinstance(data, list):
        return []

    valid_kinds = {
        "ortholog_insert",
        "branch_prune",
        "input_swap",
        "step_add",
        "step_replace",
    }
    variants: list[StructuralVariant] = []

    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "unnamed"))
        rationale = str(item.get("rationale", ""))
        raw_edits = item.get("edits", [])
        if not isinstance(raw_edits, list):
            continue

        edits: list[StructuralEdit] = []
        for e in raw_edits:
            if not isinstance(e, dict):
                continue
            kind = str(e.get("kind", ""))
            if kind not in valid_kinds:
                continue
            target = str(e.get("target_node_id", ""))
            if not target:
                continue
            edits.append(
                StructuralEdit(
                    kind=kind,
                    target_node_id=target,
                    organism=e.get("organism"),
                    search_name=e.get("search_name"),
                    parameters=e.get("parameters")
                    if isinstance(e.get("parameters"), dict)
                    else None,
                    operator=e.get("operator"),
                    description=e.get("description"),
                )
            )

        if edits:
            variants.append(
                StructuralVariant(name=name, edits=edits, rationale=rationale)
            )

    return variants[:5]


async def propose_structural_variants(
    *,
    site_id: str,
    record_type: str,
    tree: JSONObject,
    baseline_metrics: ExperimentMetrics | None,
    config: TreeOptimizationConfig,
) -> list[StructuralVariant]:
    """Call an LLM to propose structural variants for the strategy tree.

    Falls back to an empty list on any failure — structural analysis is
    best-effort and must not block the optimisation run.

    :param site_id: VEuPathDB site identifier.
    :param record_type: WDK record type.
    :param tree: The original ``PlanStepNode``-shaped dict.
    :param baseline_metrics: Baseline evaluation metrics (may be None).
    :param config: Tree optimisation config.
    :returns: Up to 5 structural variant proposals.
    """
    try:
        api = get_strategy_api(site_id)

        searches_raw: list[Any] = await api.client.get_searches(record_type)
        search_lines: list[str] = []
        for s in searches_raw[:50]:
            if isinstance(s, dict):
                sname = s.get("urlSegment") or s.get("name", "")
                sdesc = s.get("displayName", "")
                search_lines.append(f"  {sname} — {sdesc}")
        searches_summary = (
            "\n".join(search_lines) if search_lines else "(none available)"
        )

        organisms_summary = "(none configured)"
        if config.optimize_orthologs:
            try:
                ortho_details = await api.client.get_search_details(
                    record_type,
                    "GenesByOrthologs",
                )
                sd = (
                    ortho_details.get("searchData")
                    if isinstance(ortho_details, dict)
                    else None
                )
                if isinstance(sd, dict):
                    params_list = sd.get("parameters", [])
                    for p in params_list if isinstance(params_list, list) else []:
                        if isinstance(p, dict) and p.get("name") == "organism":
                            vocab = p.get("vocabulary", [])
                            if isinstance(vocab, list):
                                orgs = [
                                    v[0] if isinstance(v, list) and v else str(v)
                                    for v in vocab[:30]
                                ]
                                organisms_summary = ", ".join(orgs)
            except Exception:
                logger.debug(
                    "Could not fetch ortholog organisms for structural proposals"
                )

        tree_text = _serialise_tree_compact(tree)
        node_ids = _collect_node_ids(tree)

        baseline_summary = "Not yet evaluated"
        if baseline_metrics:
            baseline_summary = (
                f"Balanced accuracy: {baseline_metrics.balanced_accuracy:.4f}, "
                f"F1: {baseline_metrics.f1_score:.4f}, "
                f"Sensitivity: {baseline_metrics.sensitivity:.4f}, "
                f"Specificity: {baseline_metrics.specificity:.4f}, "
                f"Total results: {baseline_metrics.total_results}"
            )

        system_prompt = _build_system_prompt(
            tree_text=tree_text,
            node_ids=node_ids,
            searches_summary=searches_summary,
            organisms_summary=organisms_summary,
            baseline_summary=baseline_summary,
        )

        engine = create_engine(model_override=_MODEL_ID)
        agent = Kani(engine, system_prompt=system_prompt)

        response = await agent.chat_round_str(
            "Propose up to 5 structural variants for this strategy tree. "
            "Return ONLY a JSON array."
        )
        await agent.engine.close()

        variants = _parse_variants(response)
        logger.info(
            "LLM proposed structural variants",
            count=len(variants),
            names=[v.name for v in variants],
        )
        return variants

    except Exception as exc:
        logger.warning(
            "Structural proposal generation failed (non-fatal)",
            error=str(exc),
        )
        return []
