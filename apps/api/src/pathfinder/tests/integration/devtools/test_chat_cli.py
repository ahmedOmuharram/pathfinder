from __future__ import annotations

import json
from pathlib import Path

import pytest
import structlog

from pathfinder.devtools.chat import (
    MissingCredentialsError,
    RunArgs,
    _route_framework_logs_to_stderr,
    _wdk_token,
    parse_run_args,
    run_once,
)


def test_parse_run_args_maps_phase_models_and_run_dir(tmp_path: Path) -> None:
    args = parse_run_args(
        [
            "hello",
            "--site",
            "plasmodb",
            "--model",
            "planning=openai:gpt-4.1",
            "--run-dir",
            str(tmp_path / "r"),
        ]
    )
    assert args.prompt == "hello"
    assert args.site == "plasmodb"
    assert args.phase_models == {"planning": "openai:gpt-4.1"}
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
