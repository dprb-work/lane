from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from lane.forge_remote import (
    ForgeRemoteError,
    infer_forge_remote,
    parse_gitlab_mr_url,
    provider_from_pr_url,
)
from lane.state import LaneState


class Runner(Protocol):
    def __call__(
        self,
        argv: list[str],
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        pass


@dataclass(frozen=True)
class SyncResult:
    state: LaneState
    changes: tuple[str, ...]
    warnings: tuple[str, ...]


def sync_lane_state(
    state: LaneState,
    *,
    runner: Runner | None = None,
) -> SyncResult:
    runner = _run if runner is None else runner
    changes: list[str] = []
    warnings: list[str] = []
    updated = state

    head = _git_output(["git", "rev-parse", "HEAD"], state.path, runner)
    if head is None:
        warnings.append("current HEAD unavailable; verification freshness unchanged")
    elif state.verification is not None and (
        state.verification.head != head or state.verification.exit_status != 0
    ):
        updated = replace(updated, verification=None)
        changes.append("verification: cleared stale record")

    pr_url = updated.pr
    if pr_url is None:
        discovered, warning = _discover_change_url(updated, runner)
        if warning is not None:
            warnings.append(warning)
        if discovered is not None:
            pr_url = discovered
            updated = replace(updated, pr=discovered)
            changes.append(f"pr: {discovered}")

    if pr_url is not None:
        merged, warning = _change_is_merged(pr_url, updated.path, runner)
        if warning is not None:
            warnings.append(warning)
        if merged and updated.status != "merged":
            updated = replace(updated, status="merged")
            changes.append("status: merged")

    return SyncResult(
        state=updated,
        changes=tuple(changes),
        warnings=tuple(warnings),
    )


def _discover_change_url(
    state: LaneState,
    runner: Runner,
) -> tuple[str | None, str | None]:
    try:
        remote = infer_forge_remote(state.path, runner=runner)
    except ForgeRemoteError as error:
        return None, str(error)
    if remote.provider == "github":
        if shutil.which("gh") is None:
            return None, "PR discovery skipped; gh missing"
        result = runner(
            ["gh", "pr", "view", state.branch, "--json", "url", "--jq", ".url"],
            state.path,
        )
        if result.returncode != 0:
            return None, None
        url = result.stdout.strip()
        return (url or None), None

    if shutil.which("glab") is None:
        return None, "MR discovery skipped; glab missing"
    result = runner(
        ["glab", "mr", "view", state.branch, "--output", "json"],
        state.path,
    )
    if result.returncode != 0:
        return None, None
    return _gitlab_url(result.stdout), None


def _change_is_merged(
    pr_url: str,
    workspace: Path,
    runner: Runner,
) -> tuple[bool, str | None]:
    try:
        provider = provider_from_pr_url(pr_url)
    except ForgeRemoteError as error:
        return False, str(error)
    if provider == "github":
        if shutil.which("gh") is None:
            return False, "PR merge check skipped; gh missing"
        result = runner(["gh", "pr", "view", pr_url, "--json", "mergedAt"], workspace)
        if result.returncode != 0:
            return False, "PR merge check failed"
        try:
            raw = json.loads(result.stdout)
        except json.JSONDecodeError:
            return False, "PR merge check returned invalid JSON"
        return bool(raw.get("mergedAt")), None

    if shutil.which("glab") is None:
        return False, "MR merge check skipped; glab missing"
    try:
        mr = parse_gitlab_mr_url(pr_url)
    except ForgeRemoteError as error:
        return False, str(error)
    result = runner(
        ["glab", "mr", "view", mr.iid, "--repo", mr.repo_selector, "--output", "json"],
        workspace,
    )
    if result.returncode != 0:
        return False, "MR merge check failed"
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, "MR merge check returned invalid JSON"
    state = raw.get("state")
    return isinstance(state, str) and state.lower() == "merged", None


def _gitlab_url(output: str) -> str | None:
    try:
        raw = json.loads(output)
    except json.JSONDecodeError:
        return None
    url = raw.get("web_url") or raw.get("webUrl") or raw.get("url")
    return url if isinstance(url, str) and url else None


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
