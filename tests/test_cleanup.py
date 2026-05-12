from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lane.cleanup import (
    CleanupError,
    close_pr,
    delete_remote_branch,
    ensure_clean_worktree,
    ensure_pr_merged,
)


def test_ensure_clean_worktree_rejects_dirty_status(tmp_path: Path) -> None:
    with pytest.raises(CleanupError, match="uncommitted changes"):
        ensure_clean_worktree(
            tmp_path,
            runner=lambda argv, cwd: _result(" M file.py\n"),
        )


def test_ensure_clean_worktree_allows_dirty_when_discarding(tmp_path: Path) -> None:
    ensure_clean_worktree(
        tmp_path,
        allow_dirty=True,
        runner=lambda argv, cwd: _result(" M file.py\n"),
    )


def test_ensure_pr_merged_rejects_open_pr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.cleanup.shutil.which", lambda _: "/usr/bin/gh")

    with pytest.raises(CleanupError, match="PR is not merged"):
        ensure_pr_merged(
            "https://github.com/acme/app/pull/123",
            tmp_path,
            runner=lambda argv, cwd: _result("\n"),
        )


def test_ensure_pr_merged_rejects_missing_pr(tmp_path: Path) -> None:
    with pytest.raises(CleanupError, match="requires a PR URL"):
        ensure_pr_merged(None, tmp_path)


def test_ensure_pr_merged_accepts_merged_pr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.cleanup.shutil.which", lambda _: "/usr/bin/gh")

    ensure_pr_merged(
        "https://github.com/acme/app/pull/123",
        tmp_path,
        runner=lambda argv, cwd: _result("2026-05-12T00:00:00Z\n"),
    )


def test_close_pr_calls_gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lane.cleanup.shutil.which", lambda _: "/usr/bin/gh")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return _result("")

    close_pr("https://github.com/acme/app/pull/123", tmp_path, runner=runner)

    assert calls == [["gh", "pr", "close", "https://github.com/acme/app/pull/123"]]


def test_delete_remote_branch_calls_git(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.cleanup.shutil.which", lambda _: "/usr/bin/git")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return _result("")

    delete_remote_branch("fix/login", tmp_path, runner=runner)

    assert calls == [["git", "push", "origin", "--delete", "fix/login"]]


def _result(
    stdout: str,
    *,
    returncode: int = 0,
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["cleanup"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )
