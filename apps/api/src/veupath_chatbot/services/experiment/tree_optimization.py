"""Whole-tree strategy optimization via Optuna.

Mutates parameters across all leaf steps, boolean operators at combine nodes,
and optionally inserts ortholog transforms — then evaluates the full strategy
tree against positive/negative control genes.
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import optuna

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import StepTreeNode
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.control_tests import (
    ControlValueFormat,
    resolve_controls_param_type,
)
from veupath_chatbot.services.experiment.metrics import metrics_from_control_result
from veupath_chatbot.services.experiment.types import ExperimentMetrics

logger = get_logger(__name__)

ProgressCallback = Callable[[JSONObject], Awaitable[None]]

VALID_OPERATORS = ["INTERSECT", "UNION", "MINUS", "RMINUS"]

ORTHOLOG_SEARCH_NAME = "GenesByOrthologs"
ORTHOLOG_INPUT_PARAM = "gene_result"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TreeOptimizationConfig:
    """Configuration knobs for whole-tree optimisation."""

    budget: int = 20
    objective: str = "balanced_accuracy"
    optimize_operators: bool = True
    optimize_orthologs: bool = False
    ortholog_organisms: list[str] = field(default_factory=list)
    optimize_structure: bool = False
    parallel_concurrency: int = 3


@dataclass(slots=True)
class StructuralEdit:
    """One atomic structural change to the strategy tree."""

    kind: str  # "ortholog_insert" | "branch_prune" | "input_swap" | "step_add" | "step_replace"
    target_node_id: str
    organism: str | None = None
    search_name: str | None = None
    parameters: JSONObject | None = None
    operator: str | None = None
    description: str | None = None


@dataclass(slots=True)
class StructuralVariant:
    """A named set of structural edits proposed by the LLM."""

    name: str
    edits: list[StructuralEdit] = field(default_factory=list)
    rationale: str = ""


@dataclass(slots=True)
class TreeNodeSpec:
    """Specification for one optimisable axis on a tree node."""

    node_id: str
    param_name: str
    param_type: str  # "numeric" | "integer" | "categorical"
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    choices: list[str] | None = None


@dataclass(slots=True)
class TreeMutation:
    """A single change applied by the optimiser."""

    node_id: str
    kind: str  # "param" | "operator" | "ortholog_insert" | "branch_prune" | "input_swap" | "step_add" | "step_replace"
    field_name: str
    original_value: str
    new_value: str


@dataclass(slots=True)
class TreeOptimizationResult:
    """Result of a whole-tree optimisation run."""

    best_tree: JSONObject | None = None
    best_score: float = 0.0
    baseline_score: float = 0.0
    baseline_metrics: ExperimentMetrics | None = None
    best_metrics: ExperimentMetrics | None = None
    mutations: list[TreeMutation] = field(default_factory=list)
    total_trials: int = 0
    successful_trials: int = 0


# ---------------------------------------------------------------------------
# Evaluate a full strategy tree against controls
# ---------------------------------------------------------------------------


async def run_controls_against_tree(
    *,
    site_id: str,
    record_type: str,
    tree: JSONObject,
    controls_search_name: str,
    controls_param_name: str,
    controls_value_format: ControlValueFormat,
    positive_controls: list[str] | None = None,
    negative_controls: list[str] | None = None,
) -> JSONObject:
    """Materialise a ``PlanStepNode`` tree, intersect with controls, return metrics.

    Creates a temporary WDK strategy containing the full tree, adds an
    intersection step with each control set on top of the root, queries the
    result counts, then deletes everything.

    Returns the same shape as :func:`run_positive_negative_controls` so
    :func:`metrics_from_control_result` can consume it directly.
    """
    from veupath_chatbot.services.experiment.service import (
        _coerce_step_id,
        _materialize_step_tree,
    )

    api = get_strategy_api(site_id)

    pos = [s.strip() for s in (positive_controls or []) if s.strip()]
    neg = [s.strip() for s in (negative_controls or []) if s.strip()]

    result: JSONObject = {
        "siteId": site_id,
        "recordType": record_type,
        "target": {"searchName": "__tree__", "resultCount": None},
        "positive": None,
        "negative": None,
    }

    async def _eval_control_set(
        control_ids: list[str],
        label: str,
    ) -> JSONObject:
        """Materialise the tree, intersect with one control set, clean up."""
        root_tree = await _materialize_step_tree(api, tree, record_type)

        param_type = await resolve_controls_param_type(
            api,
            record_type,
            controls_search_name,
            controls_param_name,
        )

        controls_params: JSONObject = {}
        if param_type == "input-dataset":
            dataset_id = await api.create_dataset(control_ids)
            controls_params[controls_param_name] = str(dataset_id)
        else:
            controls_params[controls_param_name] = "\n".join(control_ids)

        controls_step = await api.create_step(
            record_type=record_type,
            search_name=controls_search_name,
            parameters=controls_params,
            custom_name=f"Controls ({label})",
        )
        controls_step_id = _coerce_step_id(controls_step)

        combined = await api.create_combined_step(
            primary_step_id=root_tree.step_id,
            secondary_step_id=controls_step_id,
            boolean_operator="INTERSECT",
            record_type=record_type,
            custom_name=f"Tree ∩ {label}",
        )
        combined_step_id = _coerce_step_id(combined)

        full_tree = StepTreeNode(
            combined_step_id,
            primary_input=root_tree,
            secondary_input=StepTreeNode(controls_step_id),
        )
        created = await api.create_strategy(
            step_tree=full_tree,
            name="Pathfinder tree eval",
            is_internal=True,
        )
        strategy_id: int | None = None
        if isinstance(created, dict):
            raw = created.get("id")
            if isinstance(raw, int):
                strategy_id = raw

        try:
            target_total = await api.get_step_count(root_tree.step_id)
            intersection_total = await api.get_step_count(combined_step_id)

            intersection_ids: list[str] = []
            if len(control_ids) <= 500:
                answer = await api.get_step_answer(
                    combined_step_id,
                    pagination={"offset": 0, "numRecords": min(len(control_ids), 500)},
                )
                if isinstance(answer, dict):
                    records = answer.get("records")
                    if isinstance(records, list):
                        for rec in records:
                            if not isinstance(rec, dict):
                                continue
                            pk = rec.get("id")
                            if isinstance(pk, list) and pk:
                                first = pk[0]
                                if isinstance(first, dict):
                                    intersection_ids.append(str(first.get("value", "")))

            return {
                "controlsCount": len(control_ids),
                "intersectionCount": intersection_total,
                "intersectionIds": list(intersection_ids),
                "intersectionIdsSample": list(intersection_ids[:50]),
                "targetStepId": root_tree.step_id,
                "targetResultCount": target_total,
            }
        finally:
            if strategy_id is not None:
                import contextlib

                with contextlib.suppress(Exception):
                    await api.delete_strategy(strategy_id)

    if pos:
        pos_payload = await _eval_control_set(pos, "positive")
        raw_count = pos_payload.get("intersectionCount")
        count = int(raw_count) if isinstance(raw_count, (int, float)) else 0
        intersection_ids_val = pos_payload.get("intersectionIds")
        found = (
            set(intersection_ids_val)
            if isinstance(intersection_ids_val, list)
            else set()
        )
        missing = [x for x in pos if found and x not in found]

        result["target"] = {
            "searchName": "__tree__",
            "resultCount": pos_payload.get("targetResultCount"),
        }
        result["positive"] = {
            **pos_payload,
            "missingIdsSample": list(missing[:50]),
            "recall": count / len(pos) if pos else None,
        }

    if neg:
        neg_payload = await _eval_control_set(neg, "negative")
        raw_count = neg_payload.get("intersectionCount")
        count = int(raw_count) if isinstance(raw_count, (int, float)) else 0
        intersection_ids_val = neg_payload.get("intersectionIds")
        hit_ids = (
            set(intersection_ids_val)
            if isinstance(intersection_ids_val, list)
            else set()
        )

        if result["target"] is None or (
            isinstance(result["target"], dict)
            and result["target"].get("resultCount") is None
        ):
            result["target"] = {
                "searchName": "__tree__",
                "resultCount": neg_payload.get("targetResultCount"),
            }
        result["negative"] = {
            **neg_payload,
            "unexpectedHitsSample": list(list(hit_ids)[:50]),
            "falsePositiveRate": count / len(neg) if neg else None,
        }

    return result


# ---------------------------------------------------------------------------
# Search-space extraction
# ---------------------------------------------------------------------------


async def _extract_search_space(
    site_id: str,
    record_type: str,
    tree: JSONObject,
    *,
    optimize_operators: bool = True,
) -> tuple[list[TreeNodeSpec], list[str]]:
    """Walk the tree and discover all optimisable axes.

    :returns: (param_specs, combine_node_ids).
    """
    api = get_strategy_api(site_id)
    specs: list[TreeNodeSpec] = []
    combine_ids: list[str] = []

    async def _walk(node: JSONObject) -> None:
        node_id = str(node.get("id", node.get("searchName", "")))
        pi = node.get("primaryInput")
        si = node.get("secondaryInput")

        if isinstance(pi, dict):
            await _walk(pi)
        if isinstance(si, dict):
            await _walk(si)

        is_combine = isinstance(pi, dict) and isinstance(si, dict)
        is_leaf = not isinstance(pi, dict) and not isinstance(si, dict)

        if is_combine and optimize_operators:
            combine_ids.append(node_id)

        if is_leaf:
            search_name = str(node.get("searchName", ""))
            if not search_name or search_name.startswith("__"):
                return
            try:
                details = await api.client.get_search_details(
                    record_type,
                    search_name,
                )
                search_data = (
                    details.get("searchData") if isinstance(details, dict) else None
                )
                if not isinstance(search_data, dict):
                    return
                params = search_data.get("parameters")
                if not isinstance(params, list):
                    return

                for p in params:
                    if not isinstance(p, dict):
                        continue
                    pname = str(p.get("name", ""))
                    ptype = str(p.get("type", ""))
                    if ptype not in ("number", "string"):
                        continue
                    is_number = p.get("isNumber") is True or ptype == "number"
                    if not is_number:
                        continue
                    min_val = _safe_float(p.get("min"))
                    max_val = _safe_float(p.get("max"))
                    step_val = _safe_float(p.get("increment") or p.get("step"))

                    init_val = _safe_float(p.get("initialDisplayValue"))
                    node_params = node.get("parameters", {})
                    cur = (
                        _safe_float(node_params.get(pname))
                        if isinstance(node_params, dict)
                        else None
                    )
                    ref = cur if cur is not None else init_val

                    if min_val is None:
                        if ref is not None:
                            min_val = 0.0 if ref >= 0 else ref * 10
                        else:
                            min_val = 0.0
                    if max_val is None:
                        max_val = ref * 10 if ref is not None and ref > 0 else 100.0
                    if min_val >= max_val:
                        max_val = min_val + 1.0

                    specs.append(
                        TreeNodeSpec(
                            node_id=node_id,
                            param_name=pname,
                            param_type="numeric",
                            min_value=min_val,
                            max_value=max_val,
                            step=step_val,
                        )
                    )
            except Exception as exc:
                logger.debug(
                    "Could not fetch param specs for search",
                    search_name=search_name,
                    error=str(exc),
                )

    await _walk(tree)
    return specs, combine_ids


def _safe_float(v: object) -> float | None:
    if v is None:
        return None
    try:
        return float(v)  # type: ignore[arg-type]
    except TypeError, ValueError:
        return None


# ---------------------------------------------------------------------------
# Tree mutation helpers
# ---------------------------------------------------------------------------


def _apply_mutations(
    tree: JSONObject,
    param_values: dict[str, dict[str, JSONValue]],
    operator_values: dict[str, str],
) -> JSONObject:
    """Return a deep copy of *tree* with mutations applied.

    :param param_values: ``{node_id: {param_name: new_value}}``.
    :param operator_values: ``{node_id: new_operator}``.
    """
    out = copy.deepcopy(tree)

    def _walk(node: JSONObject) -> None:
        node_id = str(node.get("id", node.get("searchName", "")))

        if node_id in operator_values:
            node["operator"] = operator_values[node_id]

        if node_id in param_values:
            params = node.get("parameters")
            if not isinstance(params, dict):
                params = {}
                node["parameters"] = params
            for pname, pval in param_values[node_id].items():
                params[pname] = str(pval) if isinstance(pval, float) else pval

        pi = node.get("primaryInput")
        si = node.get("secondaryInput")
        if isinstance(pi, dict):
            _walk(pi)
        if isinstance(si, dict):
            _walk(si)

    _walk(out)
    return out


def _apply_structural_edits(
    tree: JSONObject,
    edits: list[StructuralEdit],
) -> JSONObject:
    """Return a deep copy of *tree* with structural edits applied.

    Each edit modifies the tree structure (inserting, removing, or swapping
    nodes).  Edits are applied sequentially so later edits see the results
    of earlier ones.

    :param tree: ``PlanStepNode``-shaped dict.
    :param edits: Ordered structural edits to apply.
    :returns: Modified tree.
    """
    import uuid

    out = copy.deepcopy(tree)

    def _find_parent_and_slot(
        root: JSONObject,
        target_id: str,
    ) -> tuple[JSONObject | None, str | None, JSONObject | None]:
        """Find the parent node that contains ``target_id`` as a child.

        :returns: (parent, slot_key, target_node) or (None, None, target_node)
            if target is the root.
        """
        node_id = str(root.get("id", root.get("searchName", "")))
        if node_id == target_id:
            return None, None, root

        for slot in ("primaryInput", "secondaryInput"):
            child = root.get(slot)
            if isinstance(child, dict):
                child_id = str(child.get("id", child.get("searchName", "")))
                if child_id == target_id:
                    return root, slot, child
                found = _find_parent_and_slot(child, target_id)
                if found[2] is not None:
                    return found
        return None, None, None

    for edit in edits:
        parent, slot, target = _find_parent_and_slot(out, edit.target_node_id)
        if target is None:
            logger.debug(
                "Structural edit target not found", target_id=edit.target_node_id
            )
            continue

        if edit.kind == "ortholog_insert":
            new_node: JSONObject = {
                "id": f"ortho_{uuid.uuid4().hex[:8]}",
                "searchName": ORTHOLOG_SEARCH_NAME,
                "displayName": f"Orthologs ({edit.organism or '?'})",
                "parameters": {"organism": edit.organism or "", "isSyntenic": "no"},
                "primaryInput": target,
            }
            if parent is not None and slot is not None:
                parent[slot] = new_node
            else:
                out = new_node

        elif edit.kind == "branch_prune":
            pi = target.get("primaryInput")
            si = target.get("secondaryInput")
            if not isinstance(pi, dict) or not isinstance(si, dict):
                continue
            surviving = pi
            if parent is not None and slot is not None:
                parent[slot] = surviving
            else:
                out = surviving

        elif edit.kind == "input_swap":
            pi = target.get("primaryInput")
            si = target.get("secondaryInput")
            if isinstance(pi, dict) and isinstance(si, dict):
                target["primaryInput"] = si
                target["secondaryInput"] = pi

        elif edit.kind == "step_add":
            new_search: JSONObject = {
                "id": f"add_{uuid.uuid4().hex[:8]}",
                "searchName": edit.search_name or "",
                "displayName": edit.search_name or "added",
                "parameters": edit.parameters or {},
            }
            combine_node: JSONObject = {
                "id": f"comb_{uuid.uuid4().hex[:8]}",
                "searchName": "",
                "displayName": edit.operator or "INTERSECT",
                "operator": edit.operator or "INTERSECT",
                "primaryInput": target,
                "secondaryInput": new_search,
            }
            if parent is not None and slot is not None:
                parent[slot] = combine_node
            else:
                out = combine_node

        elif edit.kind == "step_replace":
            target["searchName"] = edit.search_name or target.get("searchName", "")
            if edit.search_name:
                target["displayName"] = edit.search_name
            if edit.parameters is not None:
                target["parameters"] = edit.parameters

    return out


def _collect_ids(tree: JSONObject) -> set[str]:
    """Collect all node IDs from a tree."""
    ids: set[str] = set()
    node_id = str(tree.get("id", tree.get("searchName", "")))
    if node_id:
        ids.add(node_id)
    pi = tree.get("primaryInput")
    si = tree.get("secondaryInput")
    if isinstance(pi, dict):
        ids.update(_collect_ids(pi))
    if isinstance(si, dict):
        ids.update(_collect_ids(si))
    return ids


def _diff_trees(
    original: JSONObject,
    mutated: JSONObject,
) -> list[TreeMutation]:
    """Compare two trees and return a list of mutations.

    Handles both same-shape trees (param/operator changes) and
    structurally different trees (added/removed/swapped nodes).
    """
    mutations: list[TreeMutation] = []

    def _walk(orig: JSONObject, mut: JSONObject) -> None:
        orig_id = str(orig.get("id", orig.get("searchName", "")))
        mut_id = str(mut.get("id", mut.get("searchName", "")))

        # Structural: node was replaced entirely
        if orig_id != mut_id:
            mutations.append(
                TreeMutation(
                    node_id=orig_id,
                    kind="step_replace",
                    field_name="searchName",
                    original_value=str(orig.get("searchName", "")),
                    new_value=str(mut.get("searchName", "")),
                )
            )
            return

        # Search name changed (step_replace on same ID)
        orig_search = str(orig.get("searchName", ""))
        mut_search = str(mut.get("searchName", ""))
        if orig_search and mut_search and orig_search != mut_search:
            mutations.append(
                TreeMutation(
                    node_id=orig_id,
                    kind="step_replace",
                    field_name="searchName",
                    original_value=orig_search,
                    new_value=mut_search,
                )
            )

        orig_op = str(orig.get("operator", ""))
        mut_op = str(mut.get("operator", ""))
        if orig_op and mut_op and orig_op != mut_op:
            mutations.append(
                TreeMutation(
                    node_id=orig_id,
                    kind="operator",
                    field_name="operator",
                    original_value=orig_op,
                    new_value=mut_op,
                )
            )

        orig_params = orig.get("parameters") or {}
        mut_params = mut.get("parameters") or {}
        if isinstance(orig_params, dict) and isinstance(mut_params, dict):
            for key in set(list(orig_params.keys()) + list(mut_params.keys())):
                ov = str(orig_params.get(key, ""))
                mv = str(mut_params.get(key, ""))
                if ov != mv:
                    mutations.append(
                        TreeMutation(
                            node_id=orig_id,
                            kind="param",
                            field_name=key,
                            original_value=ov,
                            new_value=mv,
                        )
                    )

        # Check for input swap (primary and secondary swapped)
        o_pi = orig.get("primaryInput")
        o_si = orig.get("secondaryInput")
        m_pi = mut.get("primaryInput")
        m_si = mut.get("secondaryInput")

        o_pi_id = (
            str(o_pi.get("id", o_pi.get("searchName", "")))
            if isinstance(o_pi, dict)
            else None
        )
        o_si_id = (
            str(o_si.get("id", o_si.get("searchName", "")))
            if isinstance(o_si, dict)
            else None
        )
        m_pi_id = (
            str(m_pi.get("id", m_pi.get("searchName", "")))
            if isinstance(m_pi, dict)
            else None
        )
        m_si_id = (
            str(m_si.get("id", m_si.get("searchName", "")))
            if isinstance(m_si, dict)
            else None
        )

        if (
            o_pi_id
            and o_si_id
            and m_pi_id
            and m_si_id
            and o_pi_id == m_si_id
            and o_si_id == m_pi_id
        ):
            mutations.append(
                TreeMutation(
                    node_id=orig_id,
                    kind="input_swap",
                    field_name="inputs",
                    original_value=f"{o_pi_id},{o_si_id}",
                    new_value=f"{m_pi_id},{m_si_id}",
                )
            )
            if isinstance(o_pi, dict) and isinstance(m_si, dict):
                _walk(o_pi, m_si)
            if isinstance(o_si, dict) and isinstance(m_pi, dict):
                _walk(o_si, m_pi)
            return

        if isinstance(o_pi, dict) and isinstance(m_pi, dict):
            _walk(o_pi, m_pi)
        elif isinstance(m_pi, dict) and not isinstance(o_pi, dict):
            mutations.append(
                TreeMutation(
                    node_id=orig_id,
                    kind="step_add",
                    field_name="primaryInput",
                    original_value="",
                    new_value=str(m_pi.get("searchName", "")),
                )
            )

        if isinstance(o_si, dict) and isinstance(m_si, dict):
            _walk(o_si, m_si)
        elif isinstance(m_si, dict) and not isinstance(o_si, dict):
            mutations.append(
                TreeMutation(
                    node_id=orig_id,
                    kind="step_add",
                    field_name="secondaryInput",
                    original_value="",
                    new_value=str(m_si.get("searchName", "")),
                )
            )

    # Detect added nodes at the structural level
    orig_ids = _collect_ids(original)
    mut_ids = _collect_ids(mutated)
    added_ids = mut_ids - orig_ids
    removed_ids = orig_ids - mut_ids

    _walk(original, mutated)

    for nid in added_ids:
        if not any(m.new_value and nid in m.new_value for m in mutations):
            mutations.append(
                TreeMutation(
                    node_id=nid,
                    kind="ortholog_insert" if "ortho_" in nid else "step_add",
                    field_name="node",
                    original_value="",
                    new_value=nid,
                )
            )

    for nid in removed_ids:
        mutations.append(
            TreeMutation(
                node_id=nid,
                kind="branch_prune",
                field_name="node",
                original_value=nid,
                new_value="",
            )
        )

    return mutations


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _score_from_metrics(
    metrics: ExperimentMetrics,
    objective: str,
) -> float:
    """Compute a scalar score from metrics for the given objective."""
    match objective:
        case "balanced_accuracy":
            return metrics.balanced_accuracy
        case "f1":
            return metrics.f1_score
        case "recall" | "sensitivity":
            return metrics.sensitivity
        case "precision":
            return metrics.precision
        case "specificity":
            return metrics.specificity
        case "mcc":
            return metrics.mcc
        case "youdens_j":
            return metrics.youdens_j
        case _:
            return metrics.balanced_accuracy


# ---------------------------------------------------------------------------
# Main optimiser
# ---------------------------------------------------------------------------


async def optimize_strategy_tree(
    *,
    site_id: str,
    record_type: str,
    tree: JSONObject,
    controls_search_name: str,
    controls_param_name: str,
    controls_value_format: ControlValueFormat,
    positive_controls: list[str] | None = None,
    negative_controls: list[str] | None = None,
    config: TreeOptimizationConfig,
    progress_callback: ProgressCallback | None = None,
) -> TreeOptimizationResult:
    """Run whole-tree Optuna optimisation.

    :param tree: The original ``PlanStepNode``-shaped dict.
    :param config: Optimisation knobs.
    :param progress_callback: Optional async callback for progress events.
    :returns: :class:`TreeOptimizationResult` with the best tree and diff.
    """
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    result = TreeOptimizationResult()

    # --- Step 1: Baseline evaluation ---
    if progress_callback:
        await progress_callback(
            {
                "type": "tree_optimization_progress",
                "data": {"phase": "baseline", "message": "Evaluating original tree..."},
            }
        )

    baseline_raw = await run_controls_against_tree(
        site_id=site_id,
        record_type=record_type,
        tree=tree,
        controls_search_name=controls_search_name,
        controls_param_name=controls_param_name,
        controls_value_format=controls_value_format,
        positive_controls=positive_controls,
        negative_controls=negative_controls,
    )
    baseline_metrics = metrics_from_control_result(baseline_raw)
    baseline_score = _score_from_metrics(baseline_metrics, config.objective)
    result.baseline_score = baseline_score
    result.baseline_metrics = baseline_metrics

    logger.info(
        "Tree optimisation baseline",
        score=baseline_score,
        f1=baseline_metrics.f1_score,
        sensitivity=baseline_metrics.sensitivity,
    )

    # --- Step 2: Extract search space ---
    if progress_callback:
        await progress_callback(
            {
                "type": "tree_optimization_progress",
                "data": {
                    "phase": "space",
                    "message": "Discovering optimisable parameters...",
                },
            }
        )

    param_specs, combine_ids = await _extract_search_space(
        site_id,
        record_type,
        tree,
        optimize_operators=config.optimize_operators,
    )

    # --- Step 2b: LLM structural analysis (optional) ---
    structural_variants: list[StructuralVariant] = []

    if config.optimize_structure:
        if progress_callback:
            await progress_callback(
                {
                    "type": "tree_optimization_progress",
                    "data": {
                        "phase": "structural_analysis",
                        "message": "AI is analysing strategy structure...",
                    },
                }
            )

        from veupath_chatbot.services.experiment.structural_proposals import (
            propose_structural_variants,
        )

        structural_variants = await propose_structural_variants(
            site_id=site_id,
            record_type=record_type,
            tree=tree,
            baseline_metrics=baseline_metrics,
            config=config,
        )

        if progress_callback:
            await progress_callback(
                {
                    "type": "tree_optimization_progress",
                    "data": {
                        "phase": "structural_analysis",
                        "message": f"AI proposed {len(structural_variants)} structural variant(s)",
                        "variantCount": len(structural_variants),
                        "variantNames": [v.name for v in structural_variants],
                    },
                }
            )

        logger.info(
            "Structural variants",
            count=len(structural_variants),
            names=[v.name for v in structural_variants],
        )

    if not param_specs and not combine_ids and not structural_variants:
        logger.info("No optimisable axes found in tree")
        result.best_tree = copy.deepcopy(tree)
        result.best_score = baseline_score
        result.best_metrics = baseline_metrics
        return result

    logger.info(
        "Tree search space",
        param_count=len(param_specs),
        operator_count=len(combine_ids),
        structural_variant_count=len(structural_variants),
    )

    # Build variant lookup: "original" + one entry per LLM proposal
    variant_names: list[str] = ["original"]
    variant_map: dict[str, StructuralVariant] = {}
    for i, sv in enumerate(structural_variants):
        key = f"variant_{i}"
        variant_names.append(key)
        variant_map[key] = sv

    # --- Step 3: Optuna study ---
    sampler = optuna.samplers.TPESampler(seed=42)
    study = optuna.create_study(direction="maximize", sampler=sampler)

    sem = asyncio.Semaphore(config.parallel_concurrency)
    budget = config.budget
    best_score = baseline_score
    best_tree = copy.deepcopy(tree)
    best_metrics = baseline_metrics
    total_trials = 0
    successful_trials = 0
    consecutive_failures = 0

    @dataclass
    class _TrialOutcome:
        score: float
        param_mutations: list[JSONObject]
        operator_mutations: list[JSONObject]
        structural_variant: str | None

    async def _run_trial(trial: optuna.trial.Trial) -> _TrialOutcome:
        """Suggest mutations, build a candidate tree, evaluate it."""
        # 1. Pick structural variant (if any are available)
        chosen_variant: str | None = None
        base_tree = tree
        if len(variant_names) > 1:
            chosen_variant = trial.suggest_categorical(
                "structural_variant",
                variant_names,
            )
            if chosen_variant != "original" and chosen_variant in variant_map:
                base_tree = _apply_structural_edits(
                    tree,
                    variant_map[chosen_variant].edits,
                )
            else:
                chosen_variant = None

        # 2. Suggest param/operator mutations
        param_values: dict[str, dict[str, JSONValue]] = {}
        operator_values: dict[str, str] = {}
        param_mutations: list[JSONObject] = []
        operator_mutations: list[JSONObject] = []

        for spec in param_specs:
            key = f"{spec.node_id}__{spec.param_name}"
            assert spec.min_value is not None and spec.max_value is not None
            val = trial.suggest_float(
                key,
                spec.min_value,
                spec.max_value,
                step=spec.step,
            )
            param_values.setdefault(spec.node_id, {})[spec.param_name] = val
            param_mutations.append(
                {
                    "nodeId": spec.node_id,
                    "param": spec.param_name,
                    "value": round(val, 4) if isinstance(val, float) else val,
                }
            )

        for cid in combine_ids:
            key = f"op__{cid}"
            op = trial.suggest_categorical(key, VALID_OPERATORS)
            operator_values[cid] = op
            operator_mutations.append({"nodeId": cid, "operator": op})

        # 3. Apply param/op mutations on top of (possibly structural) base
        candidate = _apply_mutations(base_tree, param_values, operator_values)

        # 4. Evaluate
        async with sem:
            raw = await run_controls_against_tree(
                site_id=site_id,
                record_type=record_type,
                tree=candidate,
                controls_search_name=controls_search_name,
                controls_param_name=controls_param_name,
                controls_value_format=controls_value_format,
                positive_controls=positive_controls,
                negative_controls=negative_controls,
            )

        trial_metrics = metrics_from_control_result(raw)
        score = _score_from_metrics(trial_metrics, config.objective)

        trial.set_user_attr("metrics_f1", trial_metrics.f1_score)
        trial.set_user_attr("metrics_sensitivity", trial_metrics.sensitivity)
        trial.set_user_attr("candidate_tree", candidate)
        trial.set_user_attr("trial_metrics", trial_metrics)

        return _TrialOutcome(
            score=score,
            param_mutations=param_mutations,
            operator_mutations=operator_mutations,
            structural_variant=chosen_variant,
        )

    # --- Step 4: Run trials ---
    for trial_idx in range(budget):
        if progress_callback:
            await progress_callback(
                {
                    "type": "tree_optimization_progress",
                    "data": {
                        "phase": "trial",
                        "message": f"Trial {trial_idx + 1} / {budget}",
                        "currentTrial": trial_idx + 1,
                        "totalTrials": budget,
                        "bestScore": best_score,
                    },
                }
            )

        trial = study.ask()
        total_trials += 1

        try:
            outcome = await _run_trial(trial)
            study.tell(trial, outcome.score)
            successful_trials += 1
            consecutive_failures = 0

            is_new_best = outcome.score > best_score
            if is_new_best:
                best_score = outcome.score
                candidate = trial.user_attrs.get("candidate_tree")
                if isinstance(candidate, dict):
                    best_tree = candidate
                trial_m = trial.user_attrs.get("trial_metrics")
                if isinstance(trial_m, ExperimentMetrics):
                    best_metrics = trial_m

                logger.info(
                    "New best tree found",
                    trial=trial_idx + 1,
                    score=outcome.score,
                    improvement=outcome.score - baseline_score,
                    structural_variant=outcome.structural_variant,
                )

            # Resolve structural variant display name
            sv_display: str | None = None
            if outcome.structural_variant and outcome.structural_variant in variant_map:
                sv_display = variant_map[outcome.structural_variant].name

            if progress_callback:
                await progress_callback(
                    {
                        "type": "tree_optimization_progress",
                        "data": {
                            "phase": "trial_result",
                            "currentTrial": trial_idx + 1,
                            "totalTrials": budget,
                            "bestScore": best_score,
                            "trial": {
                                "trialNumber": trial_idx + 1,
                                "score": round(outcome.score, 4),
                                "isNewBest": is_new_best,
                                "paramMutations": outcome.param_mutations,
                                "operatorMutations": outcome.operator_mutations,
                                "structuralVariant": sv_display,
                            },
                        },
                    }
                )

        except Exception as exc:
            study.tell(trial, state=optuna.trial.TrialState.FAIL)
            consecutive_failures += 1
            logger.warning(
                "Tree trial failed",
                trial=trial_idx + 1,
                error=str(exc),
            )
            if consecutive_failures >= 5 and successful_trials == 0:
                logger.error("Too many consecutive failures, aborting")
                break

        if best_score >= 0.9999:
            logger.info("Perfect score reached, stopping early")
            break

    # --- Step 5: Build result ---
    result.best_tree = best_tree
    result.best_score = best_score
    result.best_metrics = best_metrics
    result.total_trials = total_trials
    result.successful_trials = successful_trials
    result.mutations = _diff_trees(tree, best_tree)

    if progress_callback:
        await progress_callback(
            {
                "type": "tree_optimization_progress",
                "data": {
                    "phase": "complete",
                    "message": f"Optimisation complete — {len(result.mutations)} mutation(s)",
                    "bestScore": best_score,
                    "baselineScore": baseline_score,
                    "improvement": best_score - baseline_score,
                    "mutationCount": len(result.mutations),
                },
            }
        )

    return result


def tree_optimization_result_to_json(r: TreeOptimizationResult) -> JSONObject:
    """Serialize a :class:`TreeOptimizationResult` to JSON."""
    from veupath_chatbot.services.experiment.types import metrics_to_json

    return {
        "bestTree": r.best_tree,
        "bestScore": round(r.best_score, 4),
        "baselineScore": round(r.baseline_score, 4),
        "improvement": round(r.best_score - r.baseline_score, 4),
        "baselineMetrics": metrics_to_json(r.baseline_metrics)
        if r.baseline_metrics
        else None,
        "bestMetrics": metrics_to_json(r.best_metrics) if r.best_metrics else None,
        "mutations": [
            {
                "nodeId": m.node_id,
                "kind": m.kind,
                "fieldName": m.field_name,
                "originalValue": m.original_value,
                "newValue": m.new_value,
            }
            for m in r.mutations
        ],
        "totalTrials": r.total_trials,
        "successfulTrials": r.successful_trials,
    }
