from __future__ import annotations

import subprocess
from pathlib import Path

from lane.state import LaneState, VerificationState
from lane.sync import sync_lane_state


def test_sync_clears_stale_verification(tmp_path: Path) -> None:
    state = _state(
        tmp_path,
        verification=VerificationState(
            command="just verify",
            exit_status=0,
            head="oldhead",
            verified_at="2026-05-15T00:00:00+00:00",
        ),
    )

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv == ["git", "rev-parse", "HEAD"]:
            return _result(stdout="newhead\n")
        if argv == ["git", "remote", "-v"]:
            return _result(returncode=1, stderr="no remotes")
        raise AssertionError(argv)

    result = sync_lane_state(state, runner=runner)

    assert result.state.verification is None
    assert result.changes == ("verification: cleared stale record",)
    assert result.warnings == ("failed to infer forge remote: no remotes",)


def test_sync_discovers_github_pr_and_marks_merged(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state = _state(tmp_path)
    monkeypatch.setattr("lane.sync.shutil.which", lambda tool: "/usr/bin/gh")

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv == ["git", "rev-parse", "HEAD"]:
            return _result(stdout="abc123\n")
        if argv == ["git", "remote", "-v"]:
            return _result(stdout="upstream\thttps://github.com/acme/app.git (fetch)\n")
        if argv == [
            "gh",
            "pr",
            "view",
            "fix/login",
            "--json",
            "url",
            "--jq",
            ".url",
        ]:
            return _result(stdout="https://github.com/acme/app/pull/123\n")
        if argv == [
            "gh",
            "pr",
            "view",
            "https://github.com/acme/app/pull/123",
            "--json",
            "mergedAt",
        ]:
            return _result(stdout='{"mergedAt":"2026-05-15T00:00:00Z"}')
        raise AssertionError(argv)

    result = sync_lane_state(state, runner=runner)

    assert result.state.pr == "https://github.com/acme/app/pull/123"
    assert result.state.status == "merged"
    assert result.changes == (
        "pr: https://github.com/acme/app/pull/123",
        "status: merged",
    )
    assert result.warnings == ()


def test_sync_keeps_verification_when_head_is_unknown(tmp_path: Path) -> None:
    verification = VerificationState(
        command="just verify",
        exit_status=0,
        head="abc123",
        verified_at="2026-05-15T00:00:00+00:00",
    )
    state = _state(tmp_path, verification=verification)

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv == ["git", "rev-parse", "HEAD"]:
            return _result(returncode=1, stderr="not git")
        if argv == ["git", "remote", "-v"]:
            return _result(returncode=1, stderr="no remotes")
        raise AssertionError(argv)

    result = sync_lane_state(state, runner=runner)

    assert result.state.verification == verification
    assert result.changes == ()
    assert result.warnings == (
        "current HEAD unavailable; verification freshness unchanged",
        "failed to infer forge remote: no remotes",
    )


def _state(
    path: Path,
    *,
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
        pr=None,
        verification=verification,
    )


def _result(
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)
