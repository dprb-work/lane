from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lane.lane_target import LaneTargetError, resolve_lane_target
from lane.state import LaneState


def test_resolve_lane_target_prefers_existing_local_branch_lane() -> None:
    state = _state(branch="fix/login", base="release")

    target = resolve_lane_target(
        "fix/login",
        [state],
        cwd=Path("/repo"),
        runner=lambda argv, cwd: pytest.fail("remote lookup should not run"),
    )

    assert target.state == state
    assert target.branch == "fix/login"
    assert target.base == "release"


def test_resolve_lane_target_resolves_github_pr_number() -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        assert cwd == Path("/repo")
        return _result(
            '{"headRefName":"fix/login","baseRefName":"main",'
            '"url":"https://github.com/acme/app/pull/3"}'
        )

    target = resolve_lane_target("#3", [], cwd=Path("/repo"), runner=runner)

    assert target.branch == "fix/login"
    assert target.base == "main"
    assert target.pr_url == "https://github.com/acme/app/pull/3"
    assert calls == [
        ["gh", "pr", "view", "#3", "--json", "headRefName,baseRefName,url"]
    ]


def test_resolve_lane_target_resolves_gitlab_mr_url() -> None:
    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        assert argv == ["glab", "mr", "view", "3", "--output", "json"]
        assert cwd == Path("/repo")
        return _result(
            '{"source_branch":"fix/login","target_branch":"main",'
            '"web_url":"https://gitlab.com/acme/app/-/merge_requests/3"}'
        )

    target = resolve_lane_target(
        "https://gitlab.com/acme/app/-/merge_requests/3",
        [],
        cwd=Path("/repo"),
        runner=runner,
    )

    assert target.branch == "fix/login"
    assert target.base == "main"
    assert target.pr_url == "https://gitlab.com/acme/app/-/merge_requests/3"


def test_resolve_lane_target_accepts_existing_remote_branch() -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv == ["git", "remote", "-v"]:
            return _result("origin\thttps://github.com/acme/app.git (fetch)\n")
        if argv[:3] == ["git", "ls-remote", "--exit-code"]:
            return _result("abc\trefs/heads/fix/login\n")
        if argv[:2] == ["git", "symbolic-ref"]:
            return _result("refs/remotes/origin/main\n")
        raise AssertionError(argv)

    target = resolve_lane_target("fix/login", [], cwd=Path("/repo"), runner=runner)

    assert target.branch == "fix/login"
    assert target.base == "main"
    assert target.pr_url is None
    assert [
        "git",
        "ls-remote",
        "--exit-code",
        "--heads",
        "origin",
        "fix/login",
    ] in calls


def test_resolve_lane_target_rejects_missing_remote_branch() -> None:
    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv == ["git", "remote", "-v"]:
            return _result("origin\thttps://github.com/acme/app.git (fetch)\n")
        if argv[:3] == ["git", "ls-remote", "--exit-code"]:
            return _result("", returncode=2)
        raise AssertionError(argv)

    with pytest.raises(LaneTargetError, match="no lane or remote branch matches"):
        resolve_lane_target("fix/missing", [], cwd=Path("/repo"), runner=runner)


def test_resolve_lane_target_rejects_ambiguous_local_selector() -> None:
    first = _state(branch="fix/login", lane_id="login")
    second = _state(branch="chore/login", lane_id="login")

    with pytest.raises(ValueError, match="ambiguous lane selector"):
        resolve_lane_target("login", [first, second], cwd=Path("/repo"))


def _state(
    *,
    branch: str = "fix/login",
    base: str = "main",
    lane_id: str = "login",
    pr: str | None = None,
) -> LaneState:
    return LaneState(
        schema=1,
        id=lane_id,
        status="active",
        branch=branch,
        base=base,
        path=Path("/workspace"),
        spec=lane_id,
        review="none",
        pr=pr,
    )


def _result(
    stdout: str,
    *,
    returncode: int = 0,
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["lane-target"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )
