from __future__ import annotations

import subprocess
from pathlib import Path

from lane.state import LaneState, VerificationState
from lane.status import collect_status_health


def test_collect_status_health_reports_local_lane_facts(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "openspec" / "changes" / "login").mkdir(parents=True)
    state = _state(
        workspace,
        verification=VerificationState(
            command="just verify",
            exit_status=0,
            head="abc123def456",
            verified_at="2026-05-15T00:00:00+00:00",
        ),
    )

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        assert cwd == workspace
        if argv == ["git", "rev-parse", "HEAD"]:
            return _result(stdout="abc123def456\n")
        if argv == ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]:
            return _result(stdout="upstream/fix/login\n")
        if argv == ["git", "status", "--porcelain"]:
            return _result(stdout="")
        raise AssertionError(argv)

    health = collect_status_health(state, runner=runner)

    assert health.worktree == "clean"
    assert health.head == "abc123def456"
    assert health.upstream == "upstream/fix/login"
    assert health.verification == "fresh (just verify)"
    assert health.spec == "active"
    assert health.pr == "none"


def test_collect_status_health_reports_dirty_stale_and_archived(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "openspec" / "changes" / "archive" / "2026-05-15-login").mkdir(
        parents=True
    )
    state = _state(
        workspace,
        verification=VerificationState(
            command="python -m pytest",
            exit_status=0,
            head="oldhead",
            verified_at="2026-05-15T00:00:00+00:00",
        ),
    )

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv == ["git", "rev-parse", "HEAD"]:
            return _result(stdout="newhead\n")
        if argv == ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]:
            return _result(returncode=1, stderr="no upstream")
        if argv == ["git", "status", "--porcelain"]:
            return _result(stdout=" M src/app.py\n?? tests/test_app.py\n")
        raise AssertionError(argv)

    health = collect_status_health(state, runner=runner)

    assert health.worktree == "dirty (2 files)"
    assert health.head == "newhead"
    assert health.upstream == "none"
    assert health.verification == "stale (python -m pytest)"
    assert health.spec == "archived"


def test_collect_status_health_reports_github_merge_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    state = _state(workspace, pr="https://github.com/acme/app/pull/123")
    monkeypatch.setattr("lane.status.shutil.which", lambda tool: "/usr/bin/gh")

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv == ["git", "rev-parse", "HEAD"]:
            return _result(stdout="abc123\n")
        if argv == ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]:
            return _result(stdout="upstream/fix/login\n")
        if argv == ["git", "status", "--porcelain"]:
            return _result(stdout="")
        if argv == [
            "gh",
            "pr",
            "view",
            "https://github.com/acme/app/pull/123",
            "--json",
            "mergedAt,state",
        ]:
            return _result(
                stdout='{"mergedAt":"2026-05-15T00:00:00Z","state":"MERGED"}'
            )
        raise AssertionError(argv)

    assert collect_status_health(state, runner=runner).pr == "merged"


def _state(
    path: Path,
    *,
    pr: str | None = None,
    verification: VerificationState | None = None,
) -> LaneState:
    return LaneState(
        schema=1,
        id="login",
        status="active",
        branch="fix/login",
        base="main",
        path=path,
        spec="login",
        review="none",
        pr=pr,
        verification=verification,
    )


def _result(
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)
