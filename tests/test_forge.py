from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lane.forge import ForgeError, finalize_pr, infer_github_repo, pr_body
from lane.state import LaneState
from lane.verify import VerifyCommand, VerifyResult


def test_infer_github_repo_from_https_remote() -> None:
    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return _result("https://github.com/acme/app.git\n")

    assert infer_github_repo(Path("/repo"), runner=runner) == "acme/app"


def test_infer_github_repo_from_ssh_remote() -> None:
    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return _result("git@github.com:acme/app.git\n")

    assert infer_github_repo(Path("/repo"), runner=runner) == "acme/app"


def test_infer_github_repo_rejects_non_github_remote() -> None:
    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return _result("https://gitlab.com/acme/app.git\n")

    with pytest.raises(ForgeError, match="not a GitHub remote"):
        infer_github_repo(Path("/repo"), runner=runner)


def test_finalize_pr_pushes_and_creates_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lane.forge.shutil.which", lambda _: "/usr/bin/tool")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[:4] == ["git", "remote", "get-url", "origin"]:
            return _result("https://github.com/acme/app.git\n")
        if argv[:4] == ["gh", "pr", "view", "fix/login"]:
            return _result("", returncode=1)
        if argv[:3] == ["gh", "pr", "create"]:
            return _result("https://github.com/acme/app/pull/123\n")
        return _result("")

    result = finalize_pr(_state(), _verification(), runner=runner)

    assert result.pr_url == "https://github.com/acme/app/pull/123"
    assert ["git", "push", "-u", "origin", "fix/login"] in calls
    assert any(call[:3] == ["gh", "pr", "create"] for call in calls)


def test_finalize_pr_updates_existing_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lane.forge.shutil.which", lambda _: "/usr/bin/tool")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[:4] == ["git", "remote", "get-url", "origin"]:
            return _result("https://github.com/acme/app.git\n")
        if argv[:4] == ["gh", "pr", "view", "fix/login"]:
            return _result("https://github.com/acme/app/pull/123\n")
        return _result("")

    result = finalize_pr(_state(), _verification(), runner=runner)

    assert result.pr_url == "https://github.com/acme/app/pull/123"
    assert any(call[:3] == ["gh", "pr", "edit"] for call in calls)


def test_pr_body_records_verification_review_spec_and_lane() -> None:
    body = pr_body(_state(), _verification())

    assert "`just verify` exited 0" in body
    assert "Aggregate review: `approve`" in body
    assert "`login` archived/synced" in body
    assert "`/workspace`" in body


def _state() -> LaneState:
    return LaneState(
        schema=1,
        id="login",
        status="active",
        branch="fix/login",
        base="main",
        path=Path("/workspace"),
        spec="login",
        review="approve",
        pr=None,
    )


def _verification() -> VerifyResult:
    return VerifyResult(
        command=VerifyCommand(argv=["just", "verify"], label="just verify"),
        exit_status=0,
        summary="ok",
    )


def _result(
    stdout: str,
    *,
    returncode: int = 0,
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["forge"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )
