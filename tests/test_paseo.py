from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lane.paseo import (
    PaseoArchiveResult,
    PaseoError,
    PaseoWorktree,
    archive_worktree,
    create_worktree,
    list_worktrees,
    rename_current_branch,
)


def test_create_worktree_calls_paseo_branch_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.paseo.shutil.which", lambda _: "/usr/bin/paseo")
    calls: list[tuple[list[str], Path | None]] = []

    def runner(argv: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
        calls.append((argv, cwd))
        return _result(
            '{"name":"login","branchName":"fix/login","worktreePath":"/tmp/login"}'
        )

    worktree = create_worktree(
        "fix/login",
        base="main",
        cwd=Path("/repo"),
        worktree_slug="login",
        runner=runner,
    )

    assert worktree == PaseoWorktree(
        name="login",
        branch="fix/login",
        path=Path("/tmp/login"),
    )
    assert calls == [
        (
            [
                "paseo",
                "worktree",
                "create",
                "--mode",
                "branch-off",
                "--new-branch",
                "login",
                "--base",
                "main",
                "--cwd",
                "/repo",
                "--json",
            ],
            Path("/repo"),
        )
    ]


def test_rename_current_branch_renames_git_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.paseo.shutil.which", lambda _: "/usr/bin/git")
    calls: list[tuple[list[str], Path | None]] = []

    def runner(argv: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
        calls.append((argv, cwd))
        return _result("")

    rename_current_branch("fix/login", cwd=Path("/tmp/login"), runner=runner)

    assert calls == [
        (["git", "branch", "-m", "fix/login"], Path("/tmp/login")),
    ]


def test_list_worktrees_parses_paseo_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lane.paseo.shutil.which", lambda _: "/usr/bin/paseo")

    def runner(argv: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
        assert argv == ["paseo", "worktree", "ls", "--json"]
        assert cwd is None
        return _result(
            '[{"name":"login","branch":"fix/login","cwd":"/tmp/login","agent":"-"}]'
        )

    assert list_worktrees(runner=runner) == [
        PaseoWorktree(name="login", branch="fix/login", path=Path("/tmp/login"))
    ]


def test_archive_worktree_parses_paseo_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lane.paseo.shutil.which", lambda _: "/usr/bin/paseo")

    def runner(argv: list[str], cwd: Path | None) -> subprocess.CompletedProcess[str]:
        assert argv == ["paseo", "worktree", "archive", "login", "--json"]
        assert cwd is None
        return _result(
            '{"name":"login","status":"archived","removedAgents":["abc123"]}'
        )

    assert archive_worktree("login", runner=runner) == PaseoArchiveResult(
        name="login",
        removed_agents=("abc123",),
    )


def test_paseo_missing_cli_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lane.paseo.shutil.which", lambda _: None)

    with pytest.raises(PaseoError, match="paseo CLI not found"):
        list_worktrees(runner=lambda argv, cwd: _result("[]"))


def test_paseo_command_failure_raises_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lane.paseo.shutil.which", lambda _: "/usr/bin/paseo")

    with pytest.raises(PaseoError, match="daemon unavailable"):
        list_worktrees(
            runner=lambda argv, cwd: _result(
                "",
                returncode=1,
                stderr="daemon unavailable",
            )
        )


def _result(
    stdout: str,
    *,
    returncode: int = 0,
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["paseo"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )
