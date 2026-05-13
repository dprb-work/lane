from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lane.verify import VerifyCommand, VerifyError, discover_verify_command, run_verify


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
    monkeypatch.setattr("lane.verify.shutil.which", lambda _: "/usr/bin/just")
    calls: list[tuple[list[str], Path]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append((argv, cwd))
        return _result("ok\n")

    result = run_verify(tmp_path, runner=runner)

    assert calls == [(["just", "verify"], tmp_path)]
    assert result.exit_status == 0
    assert result.summary == "ok"


def test_run_verify_reports_missing_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "justfile").write_text("verify:\n  pytest\n", encoding="utf-8")
    monkeypatch.setattr("lane.verify.shutil.which", lambda _: None)

    with pytest.raises(VerifyError, match="not found on PATH"):
        run_verify(tmp_path, runner=lambda argv, cwd: _result(""))


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
