from __future__ import annotations

import argparse
import asyncio
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel
from pydantic_ai.ui.vercel_ai.request_types import (
    TextUIPart,
    ToolApprovalResponded,
    ToolApprovalRespondedPart,
    UIMessage,
)

from pathfinder.ai.agents.roles import PhaseRole
from pathfinder.ai.conversation.checkpointer import lifespan_checkpointer
from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.ai.conversation.turn_runner import run_turn
from pathfinder.ai.graph.builder import build_graph
from pathfinder.ai.memory.lifespan import lifespan_memory_store
from pathfinder.devtools import inspector
from pathfinder.devtools.capture import RunCapture, capture_tracebacks, reset_run_dir
from pathfinder.devtools.wdk_capture import capture_wdk
from pathfinder.integrations.veupathdb.auth_login import password_login
from pathfinder.jobs.auth_context import attach_user_id, attach_wdk_auth
from pathfinder.persistence.repositories.user import UserRepository
from pathfinder.platform.config import get_settings
from pathfinder.platform.db import async_session_factory
from pathfinder.services.conversations.begin import begin_conversation

DEV_USER_ID = UUID("00000000-0000-0000-0000-0000000000c1")
RUN_ROOT = Path(os.environ.get("PF_RUN_ROOT", "/data/pf-runs"))
_MAX_RESUMES = 8


class RunArgs(BaseModel):
    prompt: str
    site: str
    mode: str = "strategy"
    conversation_id: UUID
    run_dir: Path
    mock: bool = False
    approve: Literal["prompt", "auto", "deny"] = "prompt"
    capture_wdk: bool = False
    quiet: bool = False
    email: str | None = None
    password: str | None = None
    phase_models: dict[PhaseRole, str] = {}


class MissingCredentialsError(RuntimeError):
    pass


async def _wdk_token(args: RunArgs) -> str:
    """Resolve a real WDK auth token for a non-mock run. Credentials come from
    --email/--password or the WDK_DEV_EMAIL/WDK_DEV_PASSWORD env vars (set in
    .env.dev). Raises if they are missing or rejected."""

    email = args.email or os.environ.get("WDK_DEV_EMAIL")
    password = args.password or os.environ.get("WDK_DEV_PASSWORD")
    if not email or not password:
        msg = (
            "Login required for real runs. Set WDK_DEV_EMAIL and WDK_DEV_PASSWORD "
            "in .env.dev (and run with --env-file .env.dev), or pass "
            "--email/--password. Use --mock to skip login."
        )
        raise MissingCredentialsError(msg)
    token = await password_login(args.site, email, password)
    if not token:
        msg = f"WDK login failed for {email} on site {args.site!r} (bad credentials?)."
        raise MissingCredentialsError(msg)
    return token


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pathfinder.devtools.chat")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser(
        "run", help="execute one chat turn in-process, capturing artifacts"
    )
    run.add_argument("prompt")
    run.add_argument("--site", required=True)
    run.add_argument("--mode", default="strategy")
    run.add_argument("--conversation-id", default=None)
    run.add_argument("--run-dir", default=None)
    run.add_argument("--mock", action="store_true")
    run.add_argument("--approve", choices=["prompt", "auto", "deny"], default="prompt")
    run.add_argument("--capture-wdk", action="store_true")
    run.add_argument("--quiet", action="store_true")
    run.add_argument(
        "--email", default=None, help="WDK login email (else $WDK_DEV_EMAIL)"
    )
    run.add_argument(
        "--password", default=None, help="WDK login password (else $WDK_DEV_PASSWORD)"
    )
    run.add_argument("--model", action="append", default=[], metavar="PHASE=ID")

    ins = sub.add_parser("inspect", help="read a captured run directory")
    ins.add_argument("run_dir")
    ins.add_argument("--failures", action="store_true")
    ins.add_argument("--anomalies", action="store_true")
    ins.add_argument("--tree", action="store_true")
    ins.add_argument("--tool", default=None)

    diff = sub.add_parser(
        "diff", help="diff two captured runs to find the divergence point"
    )
    diff.add_argument("run_dir_a")
    diff.add_argument("run_dir_b")
    return p


def parse_run_args(argv: list[str]) -> RunArgs:
    ns = _build_parser().parse_args(["run", *argv])
    conv = UUID(ns.conversation_id) if ns.conversation_id else uuid4()
    turn_dir_name = uuid4().hex if ns.run_dir is None else ""
    run_dir = Path(ns.run_dir) if ns.run_dir else RUN_ROOT / str(conv) / turn_dir_name
    phase_models = dict(item.split("=", 1) for item in ns.model)
    return RunArgs.model_validate(
        {
            "prompt": ns.prompt,
            "site": ns.site,
            "mode": ns.mode,
            "conversation_id": conv,
            "run_dir": run_dir,
            "mock": ns.mock,
            "approve": ns.approve,
            "capture_wdk": ns.capture_wdk,
            "quiet": ns.quiet,
            "email": ns.email,
            "password": ns.password,
            "phase_models": phase_models,
        }
    )


def _route_framework_logs_to_stderr() -> None:
    """Reserve stdout for the clean trace + summary. Framework chatter uses
    structlog's default config (PrintLogger → stdout); point it at stderr so a
    caller can drop it with ``2>/dev/null`` without losing the trace."""

    structlog.configure(logger_factory=structlog.PrintLoggerFactory(file=sys.stderr))


def _user_body(args: RunArgs, *, message_id: UUID) -> ChatRequestBody:
    return ChatRequestBody(
        conversation_id=args.conversation_id,
        site_id=args.site,
        mode=args.mode,
        messages=[
            UIMessage(
                id=str(message_id), role="user", parts=[TextUIPart(text=args.prompt)]
            )
        ],
        phase_models=args.phase_models,
    )


def _resume_body(
    args: RunArgs,
    *,
    prior_assistant_id: UUID,
    tool_name: str,
    tool_call_id: str,
    approved: bool,
) -> ChatRequestBody:
    part = ToolApprovalRespondedPart(
        type=f"tool-{tool_name}",
        tool_call_id=tool_call_id,
        approval=ToolApprovalResponded(id=tool_call_id, approved=approved, reason=None),
    )
    return ChatRequestBody(
        conversation_id=args.conversation_id,
        site_id=args.site,
        mode=args.mode,
        messages=[
            UIMessage(id=str(prior_assistant_id), role="assistant", parts=[part])
        ],
        phase_models=args.phase_models,
    )


def _decide(approve: str, tool_name: str) -> bool:
    if approve == "auto":
        return True
    if approve == "deny":
        return False
    return input(
        f"⏸ approval needed: {tool_name}  approve? [y/N] "
    ).strip().lower() in {"y", "yes"}


async def _drive(
    args: RunArgs, capture: RunCapture, *, settings_url: str, wdk_token: str | None
) -> None:
    async with AsyncExitStack() as stack:
        if args.capture_wdk:
            await stack.enter_async_context(capture_wdk(capture.run_dir))
        await stack.enter_async_context(attach_wdk_auth(wdk_token))
        await stack.enter_async_context(attach_user_id(DEV_USER_ID))
        saver = await stack.enter_async_context(lifespan_checkpointer(settings_url))
        store = await stack.enter_async_context(lifespan_memory_store(settings_url))
        graph = build_graph(checkpointer=saver)
        current = _user_body(args, message_id=capture.turn_id)
        for _ in range(_MAX_RESUMES):
            await run_turn(
                body=current,
                user_id=DEV_USER_ID,
                compiled_graph=graph,
                memory_store=store,
                writer=capture,
            )
            pending = capture.pending_approval
            if pending is None:
                return
            tool_name, tool_call_id = pending
            approved = _decide(args.approve, tool_name)
            resume_id = uuid4()
            capture.turn_id = resume_id
            current = _resume_body(
                args,
                prior_assistant_id=resume_id,
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                approved=approved,
            )


async def run_once(args: RunArgs) -> int:
    _route_framework_logs_to_stderr()
    if args.mock:
        os.environ["PATHFINDER_CHAT_PROVIDER"] = "mock"
        os.environ["API_ENV"] = "test"
        get_settings.cache_clear()
    settings = get_settings()

    wdk_token = None if args.mock else await _wdk_token(args)
    if not args.quiet and wdk_token is not None:
        print(f"logged in as {args.email or os.environ.get('WDK_DEV_EMAIL')}")

    async with async_session_factory() as session:
        await UserRepository(session).get_or_create(DEV_USER_ID)
        await begin_conversation(
            session=session,
            conversation_id=args.conversation_id,
            user_id=DEV_USER_ID,
            site_id=args.site,
        )
        await session.commit()

    capture = RunCapture(
        conversation_id=args.conversation_id,
        turn_id=uuid4(),
        run_dir=args.run_dir,
        quiet=args.quiet,
    )
    reset_run_dir(args.run_dir)
    if not args.quiet:
        print(f"conversation={args.conversation_id}")
        print(f"run-dir={args.run_dir}")

    with capture_tracebacks(args.run_dir):
        await _drive(
            args, capture, settings_url=settings.database_url, wdk_token=wdk_token
        )

    capture.flush()
    _report(capture)
    return 1 if capture.has_error else 0


def _report(capture: RunCapture) -> None:
    summary = capture.summary()
    anomalies = capture.anomalies()
    print(
        f"─── summary ───  status={summary.status}  tokens={summary.tokens}  "
        f"cost=${summary.cost_usd:.3f}  toolcalls={summary.tool_calls}  "
        f"failures={summary.failures}  loop={str(summary.loop_detected).lower()}  "
        f"anomalies={len(anomalies)}"
    )
    for anomaly in anomalies:
        print(f"  ⚑ [{anomaly.severity}] {anomaly.kind}: {anomaly.message}")
    print(f"run-dir={summary.run_dir}")


def _run_inspect(ns: argparse.Namespace) -> int:
    run_dir = Path(ns.run_dir)
    if ns.tool:
        print(inspector.render_tool(run_dir, ns.tool))
    elif ns.anomalies:
        print(inspector.render_anomalies(run_dir))
    elif ns.tree:
        print(inspector.render_tree(run_dir))
    else:
        print(inspector.render_failures(run_dir))
    return 0


def main() -> None:
    argv = sys.argv[1:]
    command = argv[0] if argv else ""
    if command == "run":
        try:
            sys.exit(asyncio.run(run_once(parse_run_args(argv[1:]))))
        except MissingCredentialsError as exc:
            print(f"✖ {exc}", file=sys.stderr)
            sys.exit(2)
    ns = _build_parser().parse_args(argv)
    if ns.command == "inspect":
        sys.exit(_run_inspect(ns))
    if ns.command == "diff":
        print(inspector.render_diff(Path(ns.run_dir_a), Path(ns.run_dir_b)))
        sys.exit(0)


if __name__ == "__main__":
    main()
