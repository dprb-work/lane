from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from lane.forge_remote import (
    ForgeRemoteError,
    parse_gitlab_mr_url,
    provider_from_pr_url,
)
from lane.openspec import active_spec_path
from lane.state import LaneState


class Runner(Protocol):
    def __call__(
        self,
        argv: list[str],
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        pass


@dataclass(frozen=True)
class StatusHealth:
    worktree: str
    head: str
    upstream: str
    verification: str
    spec: str
    pr: str


def collect_status_health(
    state: LaneState,
    *,
    runner: Runner | None = None,
) -> StatusHealth:
    runner = _run if runner is None else runner
    head = _git_output(["git", "rev-parse", "HEAD"], state.path, runner)
    short_head = head[:12] if head is not None else "unknown"
    upstream = _git_output(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        state.path,
        runner,
    )
    return StatusHealth(
        worktree=_worktree_health(state.path, runner),
        head=short_head,
        upstream="none" if upstream is None else upstream,
        verification=_verification_health(state, head),
        spec=_spec_health(state.path, state.spec),
        pr=_pr_health(state.pr, state.path, runner),
    )


def _worktree_health(workspace: Path, runner: Runner) -> str:
    status = _git_output(["git", "status", "--porcelain"], workspace, runner)
    if status is None:
        return "unknown"
    changed = len([line for line in status.splitlines() if line.strip()])
    if changed == 0:
        return "clean"
    label = "file" if changed == 1 else "files"
    return f"dirty ({changed} {label})"


def _verification_health(state: LaneState, head: str | None) -> str:
    if state.verification is None:
        return "missing"
    if head is None:
        return "unknown"
    if state.verification.head == head and state.verification.exit_status == 0:
        return f"fresh ({state.verification.command})"
    return f"stale ({state.verification.command})"


def _spec_health(workspace: Path, spec: str) -> str:
    if active_spec_path(workspace, spec).exists():
        return "active"
    archive_dir = workspace / "openspec" / "changes" / "archive"
    if archive_dir.exists() and any(
        path.is_dir() and (path.name == spec or path.name.endswith(f"-{spec}"))
        for path in archive_dir.iterdir()
    ):
        return "archived"
    return "missing"


def _pr_health(pr_url: str | None, workspace: Path, runner: Runner) -> str:
    if pr_url is None:
        return "none"
    try:
        provider = provider_from_pr_url(pr_url)
    except ForgeRemoteError as error:
        return f"unknown ({error})"
    if provider == "github":
        return _github_pr_health(pr_url, workspace, runner)
    return _gitlab_mr_health(pr_url, workspace, runner)


def _github_pr_health(pr_url: str, workspace: Path, runner: Runner) -> str:
    if shutil.which("gh") is None:
        return "unknown (gh missing)"
    result = runner(
        ["gh", "pr", "view", pr_url, "--json", "mergedAt,state"],
        workspace,
    )
    if result.returncode != 0:
        return "unknown"
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return "unknown"
    if raw.get("mergedAt"):
        return "merged"
    state = raw.get("state")
    return state.lower() if isinstance(state, str) and state else "unknown"


def _gitlab_mr_health(pr_url: str, workspace: Path, runner: Runner) -> str:
    if shutil.which("glab") is None:
        return "unknown (glab missing)"
    try:
        mr = parse_gitlab_mr_url(pr_url)
    except ForgeRemoteError as error:
        return f"unknown ({error})"
    result = runner(
        ["glab", "mr", "view", mr.iid, "--repo", mr.repo_selector, "--output", "json"],
        workspace,
    )
    if result.returncode != 0:
        return "unknown"
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return "unknown"
    state = raw.get("state")
    return state.lower() if isinstance(state, str) and state else "unknown"


def _git_output(argv: list[str], cwd: Path, runner: Runner) -> str | None:
    result = runner(argv, cwd)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
