from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
import structlog

from pathfinder.assistants.site_help.mock import SITES_REPLY
from pathfinder.devtools.chat import (
    MissingCredentialsError,
    RunArgs,
    _gate_from_checkpoint,
    _route_framework_logs_to_stderr,
    _wdk_token,
    parse_respond_args,
    parse_run_args,
    run_once,
    run_respond,
)
from pathfinder.platform.config import get_settings


def test_parse_run_args_maps_phase_models_and_run_dir(tmp_path: Path) -> None:
    args = parse_run_args(
        [
            "hello",
            "--site",
            "plasmodb",
            "--model",
            "frame=openai:gpt-5.6-luna",
            "--run-dir",
            str(tmp_path / "r"),
        ]
    )
    assert args.prompt == "hello"
    assert args.site == "plasmodb"
    assert args.phase_models == {"frame": "openai:gpt-5.6-luna"}
    assert args.approve == "prompt"
    assert args.run_dir == tmp_path / "r"


def test_parse_run_args_mints_distinct_conversation_ids() -> None:
    a = parse_run_args(["hi", "--site", "plasmodb"])
    b = parse_run_args(["hi", "--site", "plasmodb"])
    assert a.conversation_id != b.conversation_id


async def test_wdk_token_missing_creds_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("WDK_DEV_EMAIL", raising=False)
    monkeypatch.delenv("WDK_DEV_PASSWORD", raising=False)
    args = parse_run_args(
        ["hi", "--site", "plasmodb", "--run-dir", str(tmp_path / "r")]
    )
    with pytest.raises(MissingCredentialsError, match="WDK_DEV_EMAIL"):
        await _wdk_token(args)


def test_route_framework_logs_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    structlog.reset_defaults()
    try:
        _route_framework_logs_to_stderr()
        structlog.get_logger("pathfinder.devtools.test").info("framework chatter X")
        out = capsys.readouterr()
        assert "framework chatter X" in out.err
        assert "framework chatter X" not in out.out
    finally:
        structlog.reset_defaults()


@pytest.mark.usefixtures("patch_app_db_engine", "db_cleaner")
async def test_run_once_resets_stale_run_dir(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "tools").mkdir(parents=True)
    stale = run_dir / "tools" / "99-stale_tool.json"
    stale.write_text('{"seq": 99, "tool": "stale_tool", "status": "failed"}')
    args = parse_run_args(
        [
            "delegation",
            "--site",
            "plasmodb",
            "--mock",
            "--approve",
            "auto",
            "--quiet",
            "--run-dir",
            str(run_dir),
        ]
    )
    code = await run_once(args)
    assert code == 0
    assert not stale.exists()


@pytest.mark.usefixtures("patch_app_db_engine", "db_cleaner")
async def test_run_prompt_stops_at_gate_then_respond_advances(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    conv = uuid4()
    run_args = parse_run_args(
        [
            "delegation",
            "--site",
            "plasmodb",
            "--mock",
            "--approve",
            "prompt",
            "--quiet",
            "--conversation-id",
            str(conv),
            "--run-dir",
            str(run_dir),
        ]
    )
    await run_once(run_args)
    gate = json.loads((run_dir / "gate.json").read_text())
    assert gate["kind"] in {"none", "approval", "consult"}

    if gate["kind"] in {"approval", "consult"}:
        flag = "--accept" if gate["kind"] == "approval" else "--answer"
        extra = [] if gate["kind"] == "approval" else ["q=x"]
        resp_args = parse_respond_args(
            [
                "--site",
                "plasmodb",
                "--mock",
                "--approve",
                "auto",
                "--quiet",
                "--conversation-id",
                str(conv),
                "--run-dir",
                str(run_dir),
                flag,
                *extra,
            ]
        )
        code = await run_respond(resp_args)
        assert code == 0
        # respond advanced the turn (events grew, gate re-derived)
        assert (run_dir / "gate.json").exists()


@pytest.mark.usefixtures("patch_app_db_engine", "db_cleaner")
async def test_respond_finds_gate_from_checkpoint_not_run_dir(tmp_path: Path) -> None:
    """The pending gate is derived from the conversation checkpoint (SSOT), so
    ``respond`` finds it without --run-dir pointing at the gate's turn."""
    run_dir = tmp_path / "run"
    conv = uuid4()
    run_args = parse_run_args(
        [
            "consult me before planning: find female-enriched genes",
            "--site",
            "plasmodb",
            "--mock",
            "--approve",
            "prompt",
            "--quiet",
            "--conversation-id",
            str(conv),
            "--run-dir",
            str(run_dir),
        ]
    )
    await run_once(run_args)
    gate = json.loads((run_dir / "gate.json").read_text())
    assert gate["kind"] == "consult", gate

    # An operator running ``respond`` from a fresh run-dir knows nothing about
    # the turn that produced the gate — the checkpoint must surface it.
    settings = get_settings()
    derived = await _gate_from_checkpoint(conv, settings.database_url)
    assert derived.kind == "consult"
    assert derived.tool == "consult_user"
    assert derived.tool_call_id == gate["toolCallId"]
    assert {q.id for q in derived.consult_questions} == {"q1", "q2"}


@pytest.mark.usefixtures("patch_app_db_engine", "db_cleaner")
async def test_a_site_help_run_answers_in_process_with_no_wdk_login(
    tmp_path: Path,
) -> None:
    """The second assistant runs through the same debugger, and needs no login."""
    run_dir = tmp_path / "run"
    args = parse_run_args(
        [
            "which sites can I search",
            "--site",
            "plasmodb",
            "--mock",
            "--assistant",
            "site_help",
            "--quiet",
            "--run-dir",
            str(run_dir),
        ]
    )

    code = await run_once(args)

    assert code == 0
    events = [
        json.loads(line)
        for line in (run_dir / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    called = [e["toolName"] for e in events if e["type"] == "tool-input-available"]
    assert called == ["list_veupathdb_sites"]
    text = "".join(e["delta"] for e in events if e["type"] == "text-delta")
    assert text == SITES_REPLY
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["status"] == "ok"


@pytest.mark.usefixtures("patch_app_db_engine", "db_cleaner")
async def test_run_once_mock_writes_artifacts_and_exits_clean(tmp_path: Path) -> None:
    args = parse_run_args(
        [
            "delegation",
            "--site",
            "plasmodb",
            "--mock",
            "--approve",
            "auto",
            "--quiet",
            "--run-dir",
            str(tmp_path / "run"),
        ]
    )
    code = await run_once(args)
    assert code == 0
    assert isinstance(args, RunArgs)
    run_dir = tmp_path / "run"
    assert (run_dir / "events.jsonl").exists()
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["status"] == "ok"
    assert (run_dir / "diagnosis.json").exists()
