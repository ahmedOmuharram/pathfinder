"""Launcher endpoints — typed forms that fire durable tools.

Per design spec ``2026-04-26-specialist-commands-design.md`` Part A.
``/optimize`` is NOT a specialist phase. It is a typed launcher that:

1. Inserts a synthetic user message carrying a ``data-optimize-launch`` part
   so the chat transcript shows the launch config card.
2. Creates a ``background_tasks`` row + defers the
   ``durable:optimize_search_parameters`` procrastinate job — the same job
   the in-graph ``@durable_tool`` would have deferred.
3. Persists a ``data-background-task-started`` chat event + ``pg_notify``
   so any SSE listener on this conversation picks up the new task.

The agent toolset no longer exposes ``optimize_search_parameters`` directly
(see ``ai/tools/toolsets/verification.py``) — this launcher is the canonical
entry point.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Path
from pydantic import JsonValue

from pathfinder.ai.agents._model_resolution import resolve_specialist_model_id
from pathfinder.ai.conversation.event_writer import ChatEventWriter
from pathfinder.ai.graph.stream_events import background_task_started_event
from pathfinder.ai.specialists.concurrency import (
    ActiveSessionConflictError,
    assert_no_active_session,
)
from pathfinder.ai.tools.standalone._optimization_models import (
    OptimizationControls,
    OptimizationSettings,
    OptimizationTarget,
)
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.ast import StrategyStepNode, walk_step_tree
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.integrations.veupathdb.discovery_service import (
    get_discovery_service,
)
from pathfinder.integrations.veupathdb.wdk_models import WDKSearchResponse
from pathfinder.jobs.app import procrastinate_app
from pathfinder.jobs.payloads import DurableTaskPayload
from pathfinder.persistence.models import User
from pathfinder.persistence.repositories.background_tasks import (
    BackgroundTaskRepository,
)
from pathfinder.persistence.repositories.message import MessagesRepository
from pathfinder.persistence.session import async_session_factory
from pathfinder.platform.errors import (
    AppError,
    ErrorCode,
    NotFoundError,
)
from pathfinder.platform.logging import get_logger
from pathfinder.services.catalog.param_adapters import (
    adapt_param_specs_from_search,
)
from pathfinder.services.experiment.store import get_experiment_store
from pathfinder.services.parameter_optimization.config import ParameterSpec
from pathfinder.services.user_preferences import set_specialist_default
from pathfinder.transport.http.deps import (
    ConversationRepo,
    CurrentUser,
)
from pathfinder.transport.http.routers._authz import (
    get_owned_conversation_or_404,
)
from pathfinder.transport.http.schemas.launchers import (
    OptimizeLaunchRequest,
    OptimizeLaunchResponse,
)

router = APIRouter(prefix="/api/v1/conversations", tags=["launchers"])
logger = get_logger(__name__)

_OPTIMIZE_TOOL_NAME = "optimize_search_parameters"
_OPTIMIZE_ESTIMATED_DURATION_SECONDS = 900
_PRECONDITION_TITLE = "Optimize launcher precondition failed"


def _precondition(*, detail: str) -> AppError:
    return AppError(
        code=ErrorCode.SPECIALIST_PRECONDITION_FAILED,
        title=_PRECONDITION_TITLE,
        status=409,
        detail=detail,
    )


def _session_conflict(conflict: ActiveSessionConflictError) -> AppError:
    return AppError(
        code=ErrorCode.SESSION_CONFLICT,
        title="Active session conflict",
        status=409,
        detail=conflict.detail,
        errors=[{"reason": conflict.reason.value}],
    )




def _load_strategy_ast(
    raw: object, conversation_id: UUID,
) -> StrategyAst:
    try:
        return StrategyAst.model_validate(raw)
    except (ValueError, TypeError) as exc:
        logger.warning(
            "optimize launcher: invalid strategy_ast",
            conversation_id=str(conversation_id),
            error=str(exc),
        )
        raise _precondition(
            detail=(
                "Conversation has no usable strategy yet. Build a "
                "strategy before launching /optimize."
            ),
        ) from exc


def _resolve_step_node(
    *, ast: StrategyAst, wdk_step_id: int,
) -> StrategyStepNode:
    """Find the AST node whose WDK-side numeric id matches ``wdk_step_id``."""
    wdk_ids = ast.wdk_step_ids or {}
    matching_local: list[str] = [
        local for local, wdk in wdk_ids.items() if wdk == wdk_step_id
    ]
    if not matching_local:
        raise _precondition(
            detail=(
                f"Step {wdk_step_id} is not built in WDK yet. Build "
                "the step before launching /optimize on it."
            ),
        )
    target_local_id = matching_local[0]
    for node in walk_step_tree(ast.root):
        if node.id == target_local_id:
            return node
    raise _precondition(
        detail=(
            f"Step {wdk_step_id} is mapped to local id "
            f"{target_local_id!r} but no node with that id exists "
            "in the strategy AST."
        ),
    )


async def _fetch_search_response(
    *, site_id: str, record_type: str, search_name: str,
) -> WDKSearchResponse:
    discovery = get_discovery_service()
    try:
        return await discovery.get_search_details(
            SearchContext(site_id, record_type, search_name),
            expand_params=True,
        )
    except AppError as exc:
        raise _precondition(
            detail=(
                f"Failed to load search '{search_name}' for record "
                f"type '{record_type}': {exc}"
            ),
        ) from exc


def _build_numeric_spec(
    name: str,
    min_v: float,
    max_v: float,
    step: float | None,
) -> ParameterSpec:
    param_type = "integer" if step == 1 else "numeric"
    return ParameterSpec.model_validate({
        "name": name,
        "type": param_type,
        "min": min_v,
        "max": max_v,
        "step": step,
    })


def _build_categorical_spec(name: str, choices: list[str]) -> ParameterSpec:
    return ParameterSpec.model_validate({
        "name": name,
        "type": "categorical",
        "choices": choices,
    })


def _parameter_specs_for_keys(
    *,
    search_response: WDKSearchResponse,
    param_keys: list[str],
    search_name: str,
) -> list[ParameterSpec]:
    """Build optimization ``ParameterSpec`` entries for each requested key.

    Validates that every key exists on the search; numeric params produce
    a continuous numeric spec, vocabulary params produce categorical with
    enumerated choices. Anything we can't turn into a sweepable spec is
    rejected so the impl never receives an under-specified ``parameter_space``.
    """
    spec_map = adapt_param_specs_from_search(search_response.search_data)
    unknown = sorted(k for k in param_keys if k not in spec_map)
    if unknown:
        raise _precondition(
            detail=(
                f"Unknown parameter(s) for search '{search_name}': "
                f"{', '.join(unknown)}"
            ),
        )
    out: list[ParameterSpec] = []
    rejected: list[str] = []
    for key in param_keys:
        normalized = spec_map[key]
        if (
            normalized.is_number
            and normalized.min is not None
            and normalized.max is not None
        ):
            out.append(
                _build_numeric_spec(
                    normalized.name,
                    normalized.min,
                    normalized.max,
                    normalized.increment,
                ),
            )
            continue
        choices = _vocabulary_choices(normalized.vocabulary)
        if choices:
            out.append(_build_categorical_spec(normalized.name, choices))
            continue
        rejected.append(normalized.name)
    if rejected:
        raise _precondition(
            detail=(
                "These parameters cannot be swept (no numeric range "
                "and no enumerated choices): "
                f"{', '.join(sorted(rejected))}"
            ),
        )
    return out


def _vocabulary_choices(vocab: object) -> list[str]:
    """Extract a flat list of vocabulary terms from a WDK vocabulary payload.

    WDK vocabularies are typically ``[[term, display, parent], ...]``;
    we keep only the term column. Tolerates missing/empty payloads.
    """
    if not isinstance(vocab, list):
        return []
    out: list[str] = []
    for entry in vocab:
        if isinstance(entry, list) and entry:
            head = entry[0]
            if isinstance(head, str) and head:
                out.append(head)
        elif isinstance(entry, str) and entry:
            out.append(entry)
    return out


async def _resolve_controls(experiment_id: str | None) -> OptimizationControls:
    """Pull positive/negative controls from a linked experiment, if any.

    Without controls the F1/objective scorer can't differentiate trials,
    so empty controls are a usability failure mode. When the conversation
    has no linked experiment we still return defaults — the sweep runs,
    trial param values are visible to the user, but trial scores will
    be uniform. The launcher logs that case.
    """
    if experiment_id is None:
        logger.info(
            "optimize launcher: no experiment linked, using empty controls",
        )
        return OptimizationControls()
    try:
        exp = await get_experiment_store().aget(experiment_id)
    except (ValueError, KeyError, RuntimeError) as exc:
        logger.warning(
            "optimize launcher: experiment lookup failed, using empty controls",
            experiment_id=experiment_id,
            error=str(exc),
        )
        return OptimizationControls()
    if exp is None:
        logger.warning(
            "optimize launcher: experiment not found, using empty controls",
            experiment_id=experiment_id,
        )
        return OptimizationControls()
    return OptimizationControls(
        positive_controls=list(exp.config.positive_controls),
        negative_controls=list(exp.config.negative_controls),
    )


def _launch_part_payload(
    body: OptimizeLaunchRequest,
    *,
    model_id: str,
    task_id: UUID,
    local_step_id: str,
) -> dict[str, object]:
    return {
        "type": "data-optimize-launch",
        "data": {
            "stepId": body.step_id,
            # Local AST step id (string) — needed by the frontend Apply
            # Best Config button to call useUpdateStepMutation, which
            # keys by local id, not the WDK numeric id.
            "localStepId": local_step_id,
            "paramKeys": list(body.param_keys),
            "criterion": body.criterion,
            "budget": body.budget,
            "modelId": model_id,
            "taskId": str(task_id),
        },
    }


def _build_durable_args(
    *,
    target: OptimizationTarget,
    controls: OptimizationControls,
    settings: OptimizationSettings,
) -> dict[str, JsonValue]:
    """Mirror ``durable._parse_invocation``'s ``{"args": [], "kwargs": {...}}`` shape.

    The worker entrypoint pulls ``args["kwargs"]`` and splats it into the
    impl, so the launcher must produce the same envelope the in-graph
    decorator would.
    """
    return {
        "args": [],
        "kwargs": {
            "target": target.model_dump(mode="json"),
            "controls": controls.model_dump(mode="json"),
            "settings": settings.model_dump(mode="json"),
        },
    }


async def _persist_started_event(
    *, conversation_id: UUID, task_id: UUID, turn_id: UUID,
) -> None:
    """Persist the ``data-background-task-started`` chunk to the chat stream.

    Writes via :class:`ChatEventWriter` (no ``task_id`` tag) so the chat SSE
    replay surfaces the chunk and the ``DataBackgroundTaskStarted`` part
    renders inline with the launcher card. Any open chat-stream tail picks
    it up via the ``conversation_events:<conv>`` ``pg_notify`` channel.
    """
    chunk = background_task_started_event(
        task_id=task_id,
        tool_name=_OPTIMIZE_TOOL_NAME,
        estimated_duration_seconds=_OPTIMIZE_ESTIMATED_DURATION_SECONDS,
    )
    writer = ChatEventWriter(
        conversation_id=conversation_id, turn_id=turn_id,
    )
    await writer.write(
        chunk.model_dump(by_alias=True, mode="json", exclude_none=True),
    )


@router.post(
    "/{conversation_id}/launchers/optimize",
    response_model=OptimizeLaunchResponse,
)
async def launch_optimize(
    conversation_id: Annotated[UUID, Path()],
    body: OptimizeLaunchRequest,
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
) -> OptimizeLaunchResponse:
    conversation = await get_owned_conversation_or_404(
        conv_repo, conversation_id, user_id,
    )
    if conversation.step_count < 1:
        raise _precondition(
            detail=(
                "Optimize requires at least one built step. Build "
                "the strategy first, then try /optimize again."
            ),
        )
    if not conversation.site_id:
        raise _precondition(
            detail="Optimize needs a selected site (PlasmoDB, ToxoDB, ...).",
        )
    try:
        await assert_no_active_session(conversation=conversation)
    except ActiveSessionConflictError as conflict:
        raise _session_conflict(conflict) from conflict

    ast = _load_strategy_ast(conversation.strategy_ast, conversation_id)
    step_node = _resolve_step_node(ast=ast, wdk_step_id=body.step_id)
    search_response = await _fetch_search_response(
        site_id=conversation.site_id,
        record_type=ast.record_type,
        search_name=step_node.search_name,
    )
    parameter_space = _parameter_specs_for_keys(
        search_response=search_response,
        param_keys=body.param_keys,
        search_name=step_node.search_name,
    )

    user = await conv_repo.session.get(User, user_id)
    if user is None:
        raise NotFoundError(title="User not found")
    model_id = await resolve_specialist_model_id(
        command="optimize", user=user, explicit=body.model_id,
    )

    target = OptimizationTarget(
        site_id=conversation.site_id,
        record_type=ast.record_type,
        search_name=step_node.search_name,
        parameter_space=[
            spec.model_dump(by_alias=True, mode="json")
            for spec in parameter_space
        ],
    )
    controls = await _resolve_controls(conversation.experiment_id)
    settings = OptimizationSettings(
        budget=body.budget,
        criterion=body.criterion,
        model_id=model_id,
    )

    durable_args = _build_durable_args(
        target=target, controls=controls, settings=settings,
    )

    repo = BackgroundTaskRepository(session_factory=async_session_factory)
    task_id = await repo.create(
        conversation_id=conversation_id,
        user_id=user_id,
        tool_name=_OPTIMIZE_TOOL_NAME,
        args=durable_args,
        estimated_duration_seconds=_OPTIMIZE_ESTIMATED_DURATION_SECONDS,
    )

    message_id = uuid4()
    await MessagesRepository(conv_repo.session).insert_message(
        message_id=message_id,
        conversation_id=conversation_id,
        role="user",
        parts=[
            _launch_part_payload(
                body,
                model_id=model_id,
                task_id=task_id,
                local_step_id=step_node.id,
            ),
        ],
        metadata={},
    )
    await set_specialist_default(
        conv_repo.session,
        user_id=user_id,
        command="optimize",
        model_id=model_id,
    )
    await conv_repo.session.commit()

    procrastinate_task = procrastinate_app.configure_task(
        name=f"durable:{_OPTIMIZE_TOOL_NAME}",
        queue="verification",
    )
    payload = DurableTaskPayload.from_context(
        task_id=task_id,
        thread_id=conversation_id,
        args=durable_args,
    )
    await procrastinate_task.defer_async(
        **payload.model_dump(mode="json", by_alias=True),
    )

    await _persist_started_event(
        conversation_id=conversation_id, task_id=task_id, turn_id=message_id,
    )

    logger.info(
        "optimize launcher fired",
        conversation_id=str(conversation_id),
        task_id=str(task_id),
        step_id=body.step_id,
        param_keys=body.param_keys,
        budget=body.budget,
    )

    return OptimizeLaunchResponse(task_id=task_id, message_id=message_id)
