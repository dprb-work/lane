from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lane.state import VerificationState
from lane.verify import (
    VerifyCommand,
    VerifyError,
    VerifyResult,
    current_head,
    discover_verify_command,
    require_fresh_verification,
    run_verify,
    verification_state,
    verify_result_from_state,
)


def test_discover_verify_prefers_justfile(tmp_path: Path) -> None:
    (tmp_path / "justfile").write_text("verify:\n  pytest\n", encoding="utf-8")
    (tmp_path / "package.json").write_text(
        '{"scripts":{"verify":"npm test"}}',
        encoding="utf-8",
    )

    assert discover_verify_command(tmp_path) == VerifyCommand(
        argv=["just", "verify"],
        label="just verify",
    )


def test_discover_verify_uses_package_json(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"scripts":{"verify":"npm test"}}',
        encoding="utf-8",
    )

    assert discover_verify_command(tmp_path) == VerifyCommand(
        argv=["npm", "run", "verify"],
        label="npm run verify",
    )


def test_discover_verify_rejects_missing_command(tmp_path: Path) -> None:
    with pytest.raises(VerifyError, match="no verify command found"):
        discover_verify_command(tmp_path)


def test_run_verify_executes_in_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "justfile").write_text("verify:\n  pytest\n", encoding="utf-8")
    monkeypatch.setattr(
        "lane.verify.shutil.which",
        lambda _, path=None: "/usr/bin/just",
    )
    calls: list[tuple[list[str], Path, bool]] = []

    def runner(
        argv: list[str],
        cwd: Path,
        env: dict[str, str],
        *,
        capture_output: bool,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((argv, cwd, capture_output))
        return _result("ok\n")

    result = run_verify(tmp_path, runner=runner)

    assert calls == [(["just", "verify"], tmp_path, True)]
    assert result.exit_status == 0
    assert result.summary == "ok"


def test_run_verify_finds_verifier_from_workspace_venv(tmp_path: Path) -> None:
    (tmp_path / "justfile").write_text("verify:\n  pytest\n", encoding="utf-8")
    just = tmp_path / ".venv" / "bin" / "just"
    just.parent.mkdir(parents=True)
    just.write_text("#!/bin/sh\n", encoding="utf-8")
    just.chmod(0o755)
    calls: list[dict[str, str]] = []

    def runner(
        argv: list[str],
        cwd: Path,
        env: dict[str, str],
        *,
        capture_output: bool,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(env)
        return _result("ok\n")

    result = run_verify(tmp_path, runner=runner)

    assert result.exit_status == 0
    assert calls[0]["VIRTUAL_ENV"] == str(tmp_path / ".venv")


def test_run_verify_reports_missing_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "justfile").write_text("verify:\n  pytest\n", encoding="utf-8")
    monkeypatch.setattr("lane.verify.shutil.which", lambda _, path=None: None)

    with pytest.raises(VerifyError, match="not found on PATH"):
        run_verify(
            tmp_path,
            runner=lambda argv, cwd, env, *, capture_output: _result(""),
        )


def test_current_head_reads_git_head(tmp_path: Path) -> None:
    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        assert argv == ["git", "rev-parse", "HEAD"]
        assert cwd == tmp_path
        return _result("abc123\n")

    assert current_head(tmp_path, runner=runner) == "abc123"


def test_verification_state_records_success_metadata() -> None:
    result = VerifyResult(
        command=VerifyCommand(argv=["just", "verify"], label="just verify"),
        exit_status=0,
        summary="ok",
    )

    state = verification_state(result, "abc123")

    assert state.command == "just verify"
    assert state.exit_status == 0
    assert state.head == "abc123"


def test_require_fresh_verification_rejects_stale_head() -> None:
    state = VerificationState(
        command="just verify",
        exit_status=0,
        head="old",
        verified_at="2026-05-15T00:00:00+00:00",
    )

    with pytest.raises(VerifyError, match="does not apply"):
        require_fresh_verification(state, "new")


def test_verify_result_from_state_preserves_command_and_status() -> None:
    state = VerificationState(
        command="just verify",
        exit_status=0,
        head="abc123",
        verified_at="2026-05-15T00:00:00+00:00",
    )

    result = verify_result_from_state(state)

    assert result.command.label == "just verify"
    assert result.exit_status == 0


def _result(
    stdout: str,
    *,
    returncode: int = 0,
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["verify"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )
