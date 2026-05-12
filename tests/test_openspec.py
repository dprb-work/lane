from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lane.openspec import (
    OpenSpecError,
    active_spec_path,
    create_spec,
    require_spec_archived,
)


def test_create_spec_calls_openspec_new_change(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lane.openspec.shutil.which", lambda _: "/usr/bin/openspec")
    calls: list[tuple[list[str], Path | None]] = []

    def runner(argv: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
        calls.append((argv, cwd))
        return _result("")

    create_spec(
        "login",
        schema="lane-lite",
        description="Lane for fix/login",
        cwd=Path("/workspace"),
        runner=runner,
    )

    assert calls == [
        (
            [
                "openspec",
                "new",
                "change",
                "login",
                "--schema",
                "lane-lite",
                "--description",
                "Lane for fix/login",
            ],
            Path("/workspace"),
        )
    ]


def test_create_spec_missing_cli_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.openspec.shutil.which", lambda _: None)

    with pytest.raises(OpenSpecError, match="openspec CLI not found"):
        create_spec(
            "login",
            schema="lane-lite",
            description="Lane for fix/login",
            cwd=Path("/workspace"),
            runner=lambda argv, cwd: _result(""),
        )


def test_create_spec_failure_raises_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lane.openspec.shutil.which", lambda _: "/usr/bin/openspec")

    with pytest.raises(OpenSpecError, match="already exists"):
        create_spec(
            "login",
            schema="lane-lite",
            description="Lane for fix/login",
            cwd=Path("/workspace"),
            runner=lambda argv, cwd: _result(
                "",
                returncode=1,
                stderr="already exists",
            ),
        )


def test_require_spec_archived_rejects_active_spec(tmp_path: Path) -> None:
    active_spec_path(tmp_path, "login").mkdir(parents=True)

    with pytest.raises(OpenSpecError, match="still active"):
        require_spec_archived(tmp_path, "login")


def test_require_spec_archived_accepts_missing_active_spec(tmp_path: Path) -> None:
    require_spec_archived(tmp_path, "login")


def _result(
    stdout: str,
    *,
    returncode: int = 0,
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["openspec"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )
