"""Standalone plan tools for pydantic-ai agents.

Provides:
- ``create_plan`` -- build a new strategy plan
- ``get_plan`` -- read the current active plan
- ``update_plan`` -- mutate the active plan in-place
- ``submit_plan`` -- present the plan for user review
- ``present_decision`` -- present a decision with options
"""

from __future__ import annotations

from datetime import UTC, datetime
from difflib import get_close_matches
from uuid import uuid4

import httpx
from pydantic import ValidationError as PydanticValidationError
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ToolReturn
from pydantic_ai.ui.vercel_ai.response_types import DataChunk
from shared_py.stream_parts.plan import (
    PlannedStep as StreamPlannedStep,
)
from shared_py.stream_parts.plan import (
    PlanSlotForm as StreamPlanSlotForm,
)
from shared_py.stream_parts.plan import (
    PlanSlotOption as StreamPlanSlotOption,
)

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.graph.state import PlanSlotAnswer
from pathfinder.ai.tools.standalone._plan_models import (
    ConnectionRef,
    DecisionOption,
    DecisionOptionInput,
    DecisionResponse,
    PlanCreatedResponse,
    PlannedConnectionInput,
    PlannedStepInput,
    StepPatch,
    UserQuestionInput,
    _apply_step_patches,
    _convert_connection,
    _convert_question,
    _convert_step,
    _validate_domain_parameters,
    _validate_domain_topology,
)
from pathfinder.ai.tools.standalone._stream_parts import (
    decision_presented_chunk,
    plan_artifact_chunk,
)
from pathfinder.ai.tools.standalone._validation_helpers import (
    validation_model_retry,
)
from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.domain.parameters.values import ParamValue, from_decoded, to_decoded
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedStep,
    PlanStatus,
    PlanTopologyError,
    StepType,
    StrategyPlan,
    UserQuestion,
)
from pathfinder.platform.errors import ValidationError, WDKError
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.platform.types import JSONObject
from pathfinder.services.catalog.param_adapters import (
    adapt_param_specs_from_search,
)
from pathfinder.services.catalog.param_discovery import fetch_search_details
from pathfinder.services.catalog.param_validation import validate_parameters
from pathfinder.services.catalog.validation_callbacks import (
    make_validation_callbacks,
)


def _validate_plan_search_names(
    deps: AgentDeps,
    steps: list[PlannedStepInput],
) -> None:
    """Raise ``ModelRetry`` with did-you-mean suggestions if any planned
    step references a search outside discovery's selected universe.

    Catches the cross-phase analogue of the ``parameter_id`` hallucination:
    the planner inventing a search name that wasn't committed in
    ``update_search_decision``. Plain ``tool_error`` would force the
    model into another full round-trip; ``ModelRetry`` re-prompts in the
    same step with a curated suggestion list.
    """
    selected = sorted(deps.agent_state.selected_search_names())
    if not selected:
        return
    bad = [
        s.search_name
        for s in steps
        if s.step_type != StepType.COMBINE
        and s.search_name
        and s.search_name not in selected
    ]
    if not bad:
        return
    suggestions = sorted(
        {
            match
            for name in bad
            for match in get_close_matches(name, selected, n=3, cutoff=0.3)
        }
    )
    msg = (
        f"Planned step(s) reference search names {bad!r} that discovery "
        f"did not select. Did you mean: {suggestions}? "
        f"Valid (selected) search names: {selected}."
    )
    raise ModelRetry(msg)


def _validate_step_parameter_keys(
    deps: AgentDeps,
    steps: list[PlannedStepInput],
) -> None:
    """Raise ``ModelRetry`` if any step's ``parameters`` dict has keys
    that aren't part of that search's discovered parameter list.

    This catches the per-step analogue of the ``parameter_id``
    hallucination in discovery — the planner inventing a parameter
    name (``minOverlap`` vs the real ``min_overlap_size``) inside a
    create_plan call. The dynamic toolset can't constrain nested dict
    keys via JSON Schema, so this body-side check fills the gap.
    """
    state = deps.agent_state
    bad_pairs: list[tuple[str, str, list[str]]] = []
    for step in steps:
        if not step.search_name or not step.parameters:
            continue
        valid = state.param_keys_for(step.search_name)
        if not valid:
            continue
        invalid = [k for k in step.parameters if k not in valid]
        if invalid:
            sorted_valid = sorted(valid)
            bad_pairs.extend((step.search_name, k, sorted_valid) for k in invalid)
    if not bad_pairs:
        return
    lines = [
        f"  - on {search_name!r}: parameter {key!r} does not exist. "
        f"Did you mean: {get_close_matches(key, valid, n=3, cutoff=0.3)}? "
        f"Valid params: {valid}"
        for search_name, key, valid in bad_pairs
    ]
    msg = "One or more planned step parameters reference unknown keys:\n" + "\n".join(
        lines
    )
    raise ModelRetry(msg)


def _validate_patch_parameter_keys(
    deps: AgentDeps,
    patches: list[StepPatch],
    existing_steps: dict[str, PlannedStep],
) -> None:
    """Same as ``_validate_step_parameter_keys`` but for ``update_plan``
    patches — uses the patch's ``search_name`` if set, else falls back
    to the existing step's ``search_name``."""
    state = deps.agent_state
    bad_pairs: list[tuple[str, str, list[str]]] = []
    for patch in patches:
        if not patch.parameters:
            continue
        existing = existing_steps.get(patch.step_id)
        search_name = patch.search_name or (existing.search_name if existing else None)
        if not search_name:
            continue
        valid = state.param_keys_for(search_name)
        if not valid:
            continue
        invalid = [k for k in patch.parameters if k not in valid]
        if invalid:
            sorted_valid = sorted(valid)
            bad_pairs.extend((search_name, k, sorted_valid) for k in invalid)
    if not bad_pairs:
        return
    lines = [
        f"  - on {search_name!r}: parameter {key!r} does not exist. "
        f"Did you mean: {get_close_matches(key, valid, n=3, cutoff=0.3)}? "
        f"Valid params: {valid}"
        for search_name, key, valid in bad_pairs
    ]
    msg = (
        "One or more update_plan patches reference unknown parameter keys:\n"
        + "\n".join(lines)
    )
    raise ModelRetry(msg)


def _validate_update_plan_inputs(
    deps: AgentDeps,
    plan: StrategyPlan,
    add_steps: list[PlannedStepInput] | None,
    step_updates: list[StepPatch] | None,
) -> None:
    """Run all four ``update_plan`` validators in one shot — keeps
    ``update_plan``'s body under the cyclomatic-complexity bar."""
    if add_steps:
        _validate_plan_search_names(deps, add_steps)
        _validate_step_parameter_keys(deps, add_steps)
    if step_updates:
        existing = {s.id: s for s in plan.steps}
        _validate_patch_search_names(deps, step_updates)
        _validate_patch_parameter_keys(deps, step_updates, existing)


def _validate_patch_search_names(
    deps: AgentDeps,
    patches: list[StepPatch],
) -> None:
    """Equivalent to ``_validate_plan_search_names`` but for the patch
    shape used by ``update_plan`` — only validates patches that try to
    override the search_name (the `existing.search_name` fallback is
    already in discovery's selected universe by virtue of having reached
    the plan in the first place)."""
    selected = sorted(deps.agent_state.selected_search_names())
    if not selected:
        return
    bad = [
        p.search_name
        for p in patches
        if p.search_name and p.search_name not in selected
    ]
    if not bad:
        return
    suggestions = sorted(
        {
            match
            for name in bad
            for match in get_close_matches(name, selected, n=3, cutoff=0.3)
        }
    )
    msg = (
        f"update_plan patches reference search names {bad!r} that "
        f"discovery did not select. Did you mean: {suggestions}? "
        f"Valid (selected) search names: {selected}."
    )
    raise ModelRetry(msg)


async def _fetch_specs_by_search(
    site_id: str,
    steps: list[PlannedStepInput],
) -> dict[str, dict[str, ParamSpecNormalized]]:
    """Fetch WDK param specs for each unique search referenced by *steps*.

    Returns ``{search_name: {param_name: ParamSpecNormalized}}``. Skips
    COMBINE steps because their synthetic ``__combine__`` search has no
    discoverable WDK schema. Any fetch failure propagates so the caller
    can surface a real discovery error instead of silently producing
    bogus specs.
    """
    unique: dict[str, PlannedStepInput] = {}
    for step in steps:
        if step.step_type == StepType.COMBINE or not step.search_name:
            continue
        if step.search_name not in unique:
            unique[step.search_name] = step

    if not unique:
        return {}

    results: dict[str, dict[str, ParamSpecNormalized]] = {}
    for search_name, step in unique.items():
        ctx = SearchContext(
            site_id=site_id,
            record_type=step.record_type,
            search_name=search_name,
        )
        response, _ = await fetch_search_details(ctx)
        results[search_name] = adapt_param_specs_from_search(response.search_data)
    return results


def _step_to_node(step: PlannedStep) -> StrategyStepNode:
    """Convert a PlannedStep to a StrategyStepNode for the artifact tree."""
    return StrategyStepNode(
        search_name=step.search_name,
        display_name=step.display_name,
        parameters={p.name: p.value for p in step.parameters if p.value is not None},
    )


def _build_proposed_plan(plan: StrategyPlan) -> JSONObject | None:
    """Build a wire-format proposedStrategyPlan from the domain plan.

    Constructs a proper step tree respecting connections. Leaf steps that
    feed into a combine step become its primary/secondary inputs.
    """
    if not plan.steps:
        return None

    step_by_id = {s.id: s for s in plan.steps}
    node_by_id: dict[str, StrategyStepNode] = {}

    # Build nodes bottom-up: leaves first, then combines.
    for step in plan.steps:
        if step.step_type == StepType.LEAF:
            node_by_id[step.id] = _step_to_node(step)

    # Wire connections: from_step feeds into to_step.
    for conn in plan.connections:
        target = step_by_id.get(conn.to_step)
        target_node = node_by_id.get(conn.to_step)
        source_node = node_by_id.get(conn.from_step)
        if target is None or source_node is None:
            continue
        if target_node is None:
            target_node = _step_to_node(target)
            node_by_id[conn.to_step] = target_node
        if target_node.primary_input is None:
            target_node.primary_input = source_node
        else:
            target_node.secondary_input = source_node

    # Find root: step that is never a from_step target, or the last step.
    target_ids = {c.to_step for c in plan.connections}
    root_id = next(
        (
            s.id
            for s in plan.steps
            if s.id not in target_ids and s.step_type != StepType.LEAF
        ),
        None,
    )
    if root_id is None:
        # Single-step plan or no combines — use the first step.
        root_id = plan.steps[0].id

    root_node = node_by_id.get(root_id)
    if root_node is None:
        root_node = _step_to_node(plan.steps[0])

    return {
        "recordType": plan.steps[0].record_type or "transcript",
        "root": root_node.model_dump(by_alias=True, exclude_none=True, mode="json"),
        "name": plan.title,
        "description": plan.description,
    }


def _normalize_question_text(value: str | None) -> str:
    """Normalize question text for semantic deduplication."""
    if value is None:
        return ""
    return " ".join(value.split()).casefold()


def _question_key(
    question: UserQuestion | UserQuestionInput,
) -> tuple[str, str, str, str]:
    """Build a stable semantic identity for a user question."""
    return (
        _normalize_question_text(question.question),
        _normalize_question_text(question.context),
        question.related_step or "",
        question.related_param or "",
    )


def _slot_questions_from_inputs(
    inputs: list[PlannedStepInput] | list[StepPatch],
) -> list[UserQuestionInput]:
    """Aggregate UserQuestionInput from any unfilled_slot with reason=needs_user_input.

    Plan-level ``questions`` is the SSOT for what the submit_plan card
    renders, so slot-level questions get hoisted there during plan
    construction/update. Returning the inputs (not domain models) lets the
    same merge dedup logic in ``_merge_questions`` apply.
    """
    out: list[UserQuestionInput] = []
    for s in inputs:
        if s.unfilled_slots is None:
            continue
        for slot in s.unfilled_slots:
            if slot.reason == "needs_user_input" and slot.question is not None:
                step_id = getattr(s, "id", None) or getattr(s, "step_id", None)
                question = slot.question.model_copy(
                    update={
                        "related_param": slot.question.related_param or slot.name,
                        "related_step": slot.question.related_step or step_id,
                    },
                )
                out.append(question)
    return out


def _merge_questions(
    existing: list[UserQuestion],
    incoming: list[UserQuestionInput],
) -> list[UserQuestion]:
    """Merge questions by semantic identity while preserving existing answers."""
    merged = list(existing)
    index_by_key = {_question_key(question): idx for idx, question in enumerate(merged)}

    for candidate in incoming:
        converted = _convert_question(candidate)
        key = _question_key(candidate)
        existing_index = index_by_key.get(key)
        if existing_index is None:
            merged.append(converted)
            index_by_key[key] = len(merged) - 1
            continue

        current = merged[existing_index]
        merged[existing_index] = converted.model_copy(
            update={
                "id": current.id,
                "answer": current.answer,
            },
        )

    return merged


def planned_steps_for_stream(plan: StrategyPlan) -> list[StreamPlannedStep]:
    """Derive stream-part PlannedStep list from a domain plan, in order."""
    return [
        StreamPlannedStep(
            order=i,
            search_name=step.search_name,
            rationale=step.rationale or None,
            parameters={
                param.name: to_decoded(param.value)
                for param in step.parameters
                if param.value is not None
            },
        )
        for i, step in enumerate(plan.steps)
    ]


def slot_forms_for_stream(plan: StrategyPlan) -> list[StreamPlanSlotForm]:
    """Derive stream-part PlanSlotForm list — one entry per NEEDS_* param.

    The submit_plan card iterates this to render inline form fields.
    NEEDS_USER_INPUT slots get an actual question + options pulled from
    the plan-level ``UserQuestion`` (matched by ``related_step`` +
    ``related_param``); NEEDS_DISCOVERY slots are surfaced for visibility
    but the form does not let the user fill them (the agent must route
    back to discovery).
    """
    questions_by_slot: dict[tuple[str, str], UserQuestion] = {
        (q.related_step, q.related_param): q
        for q in plan.questions
        if q.related_step is not None and q.related_param is not None
    }
    out: list[StreamPlanSlotForm] = []
    for step in plan.steps:
        for p in step.parameters:
            if p.status not in (
                ParamStatus.NEEDS_USER_INPUT,
                ParamStatus.NEEDS_DISCOVERY,
            ):
                continue
            question = questions_by_slot.get((step.id, p.name))
            options = [
                StreamPlanSlotOption(
                    label=opt.label,
                    value=opt.label,
                    description=opt.description,
                    recommended=opt.recommended,
                )
                for opt in (question.options if question else None) or []
            ]
            out.append(
                StreamPlanSlotForm(
                    step_id=step.id,
                    param_name=p.name,
                    param_type=p.param_type,
                    status=p.status.value,
                    required=p.required,
                    question=question.question if question else "",
                    context=question.context if question else "",
                    options=options,
                ),
            )
    return out


_CREATE_PLAN_BLOCKING_STATUSES: frozenset[PlanStatus] = frozenset(
    {PlanStatus.APPROVED, PlanStatus.EXECUTING, PlanStatus.COMPLETE},
)


async def _validate_plan_against_wdk(plan: StrategyPlan, site_id: str) -> None:
    callbacks = make_validation_callbacks(site_id)
    for step in plan.steps:
        if step.step_type != StepType.LEAF or not step.search_name:
            continue
        params: dict[str, ParamValue] = {
            p.name: p.value for p in step.parameters if p.value is not None
        }
        if not params:
            continue
        try:
            await validate_parameters(
                SearchContext(site_id, step.record_type, step.search_name),
                parameters=params,
                callbacks=callbacks,
            )
        except ValidationError as exc:
            raise validation_model_retry(
                exc,
                stepId=step.id,
                searchName=step.search_name,
                recordType=step.record_type,
            ) from exc


def _topology_error_message(
    exc: PydanticValidationError | PlanTopologyError,
) -> str:
    if isinstance(exc, PlanTopologyError):
        return str(exc)
    for err in exc.errors():
        ctx = err.get("ctx") or {}
        inner = ctx.get("error")
        if isinstance(inner, PlanTopologyError):
            return str(inner)
        msg = err.get("msg")
        if msg:
            return str(msg)
    return str(exc)


async def create_plan(
    ctx: RunContext[AgentDeps],
    title: str,
    description: str,
    rationale: str,
    steps: list[PlannedStepInput],
    connections: list[PlannedConnectionInput],
    questions: list[UserQuestionInput] | None = None,
    uncertainties: list[str] | None = None,
) -> ToolReturn[PlanCreatedResponse] | ToolErrorPayload:
    """Create a new strategy plan and set it as the active plan.

    Returns an acknowledgment — NOT the full plan. The user cannot see the
    plan until you call submit_plan(). You can review with get_plan and
    refine with update_plan before submitting.

    Args:
        title: Plan title.
        description: What this strategy finds and why.
        rationale: Why this approach was chosen.
        steps: Planned steps.
        connections: Step connections.
        questions: Questions for the user.
        uncertainties: Things we don't know yet.
    """
    existing = ctx.deps.agent_state.active_plan
    if existing is not None and existing.status in _CREATE_PLAN_BLOCKING_STATUSES:
        msg = (
            f"PLAN_ALREADY_EXISTS: A {existing.status.value} plan already exists "
            f"(id={existing.id}, title={existing.title!r}). "
            "Use update_plan to modify it or submit_plan to re-present."
        )
        raise ModelRetry(msg)

    _validate_plan_search_names(ctx.deps, steps)
    _validate_step_parameter_keys(ctx.deps, steps)

    try:
        specs_by_search = await _fetch_specs_by_search(ctx.deps.site_id, steps)
    except (httpx.HTTPError, WDKError) as exc:
        return tool_error(
            "DISCOVERY_ERROR",
            f"Failed to fetch WDK param specs for plan: {exc}",
        )
    try:
        domain_steps = [
            _convert_step(s, param_specs=specs_by_search.get(s.search_name))
            for s in steps
        ]
    except ValueError as exc:
        msg = f"DISCOVERY_ERROR: {exc}"
        raise ModelRetry(msg) from exc
    domain_connections = [_convert_connection(c) for c in connections]
    slot_questions = _slot_questions_from_inputs(steps)
    domain_questions = _merge_questions([], (questions or []) + slot_questions)

    try:
        plan = StrategyPlan(
            title=title,
            description=description,
            rationale=rationale,
            status=PlanStatus.DRAFT,
            steps=domain_steps,
            connections=domain_connections,
            questions=domain_questions,
            uncertainties=uncertainties or [],
        )
    except (PydanticValidationError, PlanTopologyError) as exc:
        msg = f"TOPOLOGY_ERROR: {_topology_error_message(exc)}"
        raise ModelRetry(msg) from exc

    _validate_domain_parameters(plan, ctx.deps.agent_state)
    await _validate_plan_against_wdk(plan, ctx.deps.site_id)
    ctx.deps.agent_state.set_plan(plan)

    proposed_plan = _build_proposed_plan(plan)

    artifact = {
        "id": plan.id,
        "title": plan.title,
        "summaryMarkdown": plan.description,
        "assumptions": plan.uncertainties or [],
        "proposedStrategyPlan": proposed_plan,
        "createdAt": datetime.now(UTC).isoformat(),
    }

    return ToolReturn(
        return_value=PlanCreatedResponse(
            plan_id=plan.id,
            title=plan.title,
            step_count=len(plan.steps),
            planning_artifact=artifact,
        ),
        metadata=[
            plan_artifact_chunk(
                plan_id=plan.id,
                steps=planned_steps_for_stream(plan),
                rationale=plan.rationale or "",
                slots=slot_forms_for_stream(plan),
            ),
        ],
    )


async def get_plan(
    ctx: RunContext[AgentDeps],
) -> StrategyPlan:
    """Read the current active strategy plan. Use this to review the plan before making updates."""
    plan = ctx.deps.agent_state.active_plan
    if plan is None:
        msg = "NO_ACTIVE_PLAN: No plan exists yet. Call create_plan first."
        raise ModelRetry(msg)
    return plan


def _mutate_plan(
    plan: StrategyPlan,
    *,
    title: str | None,
    description: str | None,
    step_updates: list[StepPatch] | None,
    add_steps: list[PlannedStepInput] | None,
    remove_steps: list[str] | None,
    add_connections: list[PlannedConnectionInput] | None,
    remove_connections: list[ConnectionRef] | None,
    questions: list[UserQuestionInput] | None,
    specs_by_search: dict[str, dict[str, ParamSpecNormalized]] | None = None,
) -> None:
    """Apply all mutations to a plan in-place. Raises ModelRetry on bad patches."""
    if title is not None:
        plan.title = title
    if description is not None:
        plan.description = description

    if remove_steps:
        remove_set = set(remove_steps)
        plan.steps = [s for s in plan.steps if s.id not in remove_set]
        plan.connections = [
            c
            for c in plan.connections
            if c.from_step not in remove_set and c.to_step not in remove_set
        ]

    if step_updates:
        _apply_step_patches(
            plan,
            step_updates,
            specs_by_search=specs_by_search,
        )

    if add_steps:
        plan.steps.extend(
            _convert_step(
                s,
                param_specs=specs_by_search.get(s.search_name)
                if specs_by_search
                else None,
            )
            for s in add_steps
        )

    if remove_connections:
        remove_pairs = {(r.from_step, r.to_step) for r in remove_connections}
        plan.connections = [
            c for c in plan.connections if (c.from_step, c.to_step) not in remove_pairs
        ]

    if add_connections:
        plan.connections.extend(_convert_connection(c) for c in add_connections)

    if questions is not None:
        plan.questions = _merge_questions(plan.questions, questions)


async def update_plan(
    ctx: RunContext[AgentDeps],
    step_updates: list[StepPatch] | None = None,
    add_steps: list[PlannedStepInput] | None = None,
    remove_steps: list[str] | None = None,
    add_connections: list[PlannedConnectionInput] | None = None,
    remove_connections: list[ConnectionRef] | None = None,
    title: str | None = None,
    description: str | None = None,
    questions: list[UserQuestionInput] | None = None,
) -> ToolReturn[StrategyPlan] | ToolErrorPayload:
    """Mutate the active plan in-place. Apply step patches, add/remove steps and connections.

    The plan stays in the tool loop — chain multiple update_plan calls, then
    call submit_plan when ready to show the user.

    Args:
        step_updates: Patches to existing steps (by step id). Merges parameters.
        add_steps: New steps to add to the plan.
        remove_steps: Step IDs to remove from the plan.
        add_connections: New connections to add.
        remove_connections: Connections to remove (by from_step + to_step).
        title: New plan title.
        description: New plan description.
        questions: User-facing questions to merge into the plan before presentation.
    """
    plan = ctx.deps.agent_state.active_plan
    if plan is None:
        msg = "NO_ACTIVE_PLAN: No plan exists yet. Call create_plan first."
        raise ModelRetry(msg)

    _validate_update_plan_inputs(ctx.deps, plan, add_steps, step_updates)

    # Fetch WDK specs for any new or patched steps. unfilled_slots-only
    # patches need specs too — _build_unfilled_param requires the spec to
    # construct the PlannedParameter (raises ValueError otherwise).
    enrichable_steps = list(add_steps or [])
    if step_updates:
        step_map = {s.id: s for s in plan.steps}
        for patch in step_updates:
            existing = step_map.get(patch.step_id)
            needs_spec = patch.parameters or patch.unfilled_slots
            if existing is not None and needs_spec:
                enrichable_steps.append(
                    PlannedStepInput(
                        search_name=patch.search_name or existing.search_name,
                        display_name=existing.display_name,
                        record_type=existing.record_type,
                        step_type=existing.step_type,
                    ),
                )
    try:
        specs_by_search = await _fetch_specs_by_search(
            ctx.deps.site_id,
            enrichable_steps,
        )
    except (httpx.HTTPError, WDKError) as exc:
        return tool_error(
            "DISCOVERY_ERROR",
            f"Failed to fetch WDK param specs for plan update: {exc}",
        )

    slot_questions = _slot_questions_from_inputs(
        list(add_steps or []),
    ) + _slot_questions_from_inputs(list(step_updates or []))
    aggregated_questions = list(questions or []) + slot_questions

    candidate = plan.model_copy(deep=True)
    try:
        _mutate_plan(
            candidate,
            title=title,
            description=description,
            step_updates=step_updates,
            add_steps=add_steps,
            remove_steps=remove_steps,
            add_connections=add_connections,
            remove_connections=remove_connections,
            questions=aggregated_questions or None,
            specs_by_search=specs_by_search,
        )
    except ValueError as exc:
        msg = f"DISCOVERY_ERROR: {exc}"
        raise ModelRetry(msg) from exc

    _validate_domain_topology(candidate)
    _validate_domain_parameters(candidate, ctx.deps.agent_state)
    await _validate_plan_against_wdk(candidate, ctx.deps.site_id)

    candidate.version += 1
    candidate.updated_at = datetime.now(UTC)
    ctx.deps.agent_state.active_plan = candidate

    return ToolReturn(
        return_value=candidate,
        metadata=[
            plan_artifact_chunk(
                plan_id=candidate.id,
                steps=planned_steps_for_stream(candidate),
                rationale=candidate.rationale or "",
                slots=slot_forms_for_stream(candidate),
            ),
        ],
    )


async def submit_plan(
    ctx: RunContext[AgentDeps],
) -> ToolReturn[StrategyPlan]:
    """Submit the current plan for user approval.

    Registered with ``requires_approval=True`` so pydantic-ai halts the
    agent with a ``DeferredToolRequests`` on the first call. The adapter
    emits a ``ToolApprovalRequestChunk``; the backend writes a
    ``PendingApproval`` onto graph state and hands the turn back to the
    user. The submit_plan card surfaces NEEDS_USER_INPUT slots as inline
    form fields. On approval, the next turn carries an
    ``approval-responded`` part PLUS a sibling ``data-plan-slot-answers``
    part with the form values.  This body resumes with
    ``DeferredToolResults(approvals={id: True})``, applies slot answers
    via ``deps.plan_slot_answers``, refuses if any NEEDS_DISCOVERY remain
    (Stage F), then sets status=APPROVED.

    Call after create_plan or update_plan.
    """
    deps = ctx.deps
    plan = deps.agent_state.active_plan
    if plan is None:
        msg = "NO_ACTIVE_PLAN: No plan exists yet. Call create_plan first."
        raise ModelRetry(msg)

    _apply_slot_answers_to_plan(plan, deps.plan_slot_answers)
    _refuse_if_unresolved_slots(plan)

    plan.status = PlanStatus.APPROVED
    plan.updated_at = datetime.now(UTC)

    metadata: list[DataChunk] = [
        plan_artifact_chunk(
            plan_id=plan.id,
            steps=planned_steps_for_stream(plan),
            rationale=plan.rationale or "",
            slots=slot_forms_for_stream(plan),
        ),
    ]

    return ToolReturn(return_value=plan, metadata=metadata)


def _apply_slot_answers_to_plan(
    plan: StrategyPlan,
    answers: list[PlanSlotAnswer],
) -> None:
    if not answers:
        return
    step_map = {s.id: s for s in plan.steps}
    for ans in answers:
        step = step_map.get(ans.step_id)
        if step is None:
            continue
        param = next(
            (p for p in step.parameters if p.name == ans.param_name),
            None,
        )
        if param is None:
            continue
        param.value = from_decoded(param.param_type, ans.value)
        param.status = ParamStatus.USER_SET
    answered_keys = {(a.step_id, a.param_name) for a in answers}
    for q in plan.questions:
        if q.related_step is None or q.related_param is None:
            continue
        key = (q.related_step, q.related_param)
        if key in answered_keys:
            value = next(a.value for a in answers if (a.step_id, a.param_name) == key)
            q.answer = value


def _refuse_if_unresolved_slots(plan: StrategyPlan) -> None:
    """Stage F: refuse submission if any param still NEEDS_DISCOVERY.

    NEEDS_USER_INPUT slots that weren't answered are also refused —
    they're a contract failure (the form must be fully filled before
    approve). The agent must update_plan to either route back through
    discovery (NEEDS_DISCOVERY) or rephrase the question
    (NEEDS_USER_INPUT). The refusal payload tells the agent which slots
    are blocking.

    The Lead reads the open slots from the Ledger and routes accordingly.
    """
    blocking: list[tuple[str, str, ParamStatus]] = [
        (step.id, p.name, p.status)
        for step in plan.steps
        for p in step.parameters
        if p.status in (ParamStatus.NEEDS_DISCOVERY, ParamStatus.NEEDS_USER_INPUT)
    ]
    if not blocking:
        return
    summary = ", ".join(
        f"{sid}.{pname}={status.value}" for sid, pname, status in blocking
    )
    msg = (
        f"UNRESOLVED_SLOTS: Plan has unresolved slots — {summary}. "
        "NEEDS_DISCOVERY: route back to discovery to enumerate vocab. "
        "NEEDS_USER_INPUT: the user did not fill the form field; "
        "rephrase the question or convert to NEEDS_DISCOVERY."
    )
    raise ModelRetry(msg)


async def present_decision(
    ctx: RunContext[AgentDeps],
    question: str,
    options: list[DecisionOptionInput],
    context: str,
    recommendation: str | None = None,
) -> ToolReturn[DecisionResponse]:
    """Present a decision with options for the user to choose from.

    Unlike submit_plan, this does NOT pause the tool loop. The decision
    is emitted to the UI for display but execution continues. Use when
    you need to inform the user of a trade-off or ask a non-blocking
    question while continuing other work.

    Args:
        question: The decision question.
        options: Options with pros/cons.
        context: Why this decision matters.
        recommendation: Your recommended option.
    """
    decision_id = f"decision_{uuid4().hex[:12]}"

    response = DecisionResponse(
        decision_id=decision_id,
        question=question,
        options=[
            DecisionOption(
                label=opt.label,
                description=opt.description,
                pros=opt.pros,
                cons=opt.cons,
                recommended=opt.recommended,
            )
            for opt in options
        ],
        context=context,
        recommendation=recommendation,
    )

    return ToolReturn(
        return_value=response,
        metadata=[
            decision_presented_chunk(
                decision_type=decision_id,
                options=response.options,
                rationale=response.context or recommendation,
            ),
        ],
    )
