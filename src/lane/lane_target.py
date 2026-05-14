from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from lane.forge_remote import ForgeRemoteError, infer_forge_remote
from lane.resolve import resolve_exact_branch, resolve_pr_selector, resolve_slug
from lane.selectors import is_pr_selector, pr_number
from lane.state import LaneState


class LaneTargetError(RuntimeError):
    pass


@dataclass(frozen=True)
class LaneTarget:
    selector: str
    branch: str
    base: str
    pr_url: str | None
    state: LaneState | None = None


class Runner(Protocol):
    def __call__(
        self,
        argv: list[str],
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        pass


def resolve_lane_target(
    selector: str,
    lanes: list[LaneState],
    *,
    cwd: Path,
    runner: Runner | None = None,
) -> LaneTarget:
    """Resolve local and remote lane selectors in one shared code path."""
    local = _resolve_local_target(selector, lanes)
    if local is not None:
        return local

    runner = _run if runner is None else runner
    if is_pr_selector(selector):
        return _resolve_provider_lane_target(selector, cwd, runner)
    if "/" in selector:
        if not _remote_branch_exists(selector, cwd, runner):
            raise LaneTargetError(
                f"no lane or remote branch matches {selector!r}"
            )
        return LaneTarget(
            selector=selector,
            branch=selector,
            base=_default_base(cwd, runner),
            pr_url=None,
        )
    raise LaneTargetError(f"no lane matches {selector!r}")


def _resolve_local_target(
    selector: str,
    lanes: list[LaneState],
) -> LaneTarget | None:
    try:
        if is_pr_selector(selector):
            state = resolve_pr_selector(selector, lanes)
        elif "/" in selector:
            state = resolve_exact_branch(selector, lanes)
        else:
            state = resolve_slug(selector, lanes)
    except ValueError as error:
        if "ambiguous lane selector" in str(error):
            raise
        return None
    return LaneTarget(
        selector=selector,
        branch=state.branch,
        base=state.base,
        pr_url=state.pr,
        state=state,
    )


def _resolve_provider_lane_target(
    selector: str,
    cwd: Path,
    runner: Runner,
) -> LaneTarget:
    parsed = urlparse(selector)
    if parsed.hostname == "gitlab.com" or "merge_requests" in parsed.path:
        return _resolve_gitlab_mr(selector, cwd, runner)
    return _resolve_github_pr(selector, cwd, runner)


def _resolve_github_pr(selector: str, cwd: Path, runner: Runner) -> LaneTarget:
    result = _run_required(
        ["gh", "pr", "view", selector, "--json", "headRefName,baseRefName,url"],
        cwd,
        runner,
        tool="gh pr view",
    )
    raw = _json_object(result.stdout, "gh pr view")
    branch = _required_str(raw, "headRefName", "gh pr view")
    base = _required_str(raw, "baseRefName", "gh pr view")
    return LaneTarget(
        selector=selector,
        branch=branch,
        base=base,
        pr_url=_optional_str(raw, "url"),
    )


def _resolve_gitlab_mr(selector: str, cwd: Path, runner: Runner) -> LaneTarget:
    target = pr_number(selector) or selector
    result = _run_required(
        ["glab", "mr", "view", target, "--output", "json"],
        cwd,
        runner,
        tool="glab mr view",
    )
    raw = _json_object(result.stdout, "glab mr view")
    branch = _first_str(raw, ("source_branch", "sourceBranch"), "glab mr view")
    base = _first_str(raw, ("target_branch", "targetBranch"), "glab mr view")
    return LaneTarget(
        selector=selector,
        branch=branch,
        base=base,
        pr_url=_optional_str(raw, "web_url") or _optional_str(raw, "webUrl"),
    )


def _remote_branch_exists(branch: str, cwd: Path, runner: Runner) -> bool:
    try:
        remote = infer_forge_remote(cwd, runner=runner)
    except ForgeRemoteError as error:
        raise LaneTargetError(str(error)) from error
    result = runner(
        ["git", "ls-remote", "--exit-code", "--heads", remote.name, branch],
        cwd,
    )
    return result.returncode == 0


def _default_base(cwd: Path, runner: Runner) -> str:
    try:
        remote = infer_forge_remote(cwd, runner=runner)
    except ForgeRemoteError:
        return "main"
    result = runner(["git", "symbolic-ref", f"refs/remotes/{remote.name}/HEAD"], cwd)
    if result.returncode != 0:
        return "main"
    base = result.stdout.strip().rsplit("/", maxsplit=1)[-1]
    return base or "main"


def _run_required(
    argv: list[str],
    cwd: Path,
    runner: Runner,
    *,
    tool: str,
) -> subprocess.CompletedProcess[str]:
    result = runner(argv, cwd)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise LaneTargetError(f"{tool} failed: {message}")
    return result


def _json_object(raw: str, tool: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise LaneTargetError(f"{tool} returned invalid JSON") from error
    if not isinstance(value, dict):
        raise LaneTargetError(f"{tool} returned invalid JSON")
    return value


def _required_str(raw: dict[str, object], key: str, tool: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or value == "":
        raise LaneTargetError(f"{tool} response missing {key!r}")
    return value


def _optional_str(raw: dict[str, object], key: str) -> str | None:
    value = raw.get(key)
    return value if isinstance(value, str) and value != "" else None


def _first_str(raw: dict[str, object], keys: tuple[str, ...], tool: str) -> str:
    for key in keys:
        value = _optional_str(raw, key)
        if value is not None:
            return value
    expected = " or ".join(repr(key) for key in keys)
    raise LaneTargetError(f"{tool} response missing {expected}")


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
