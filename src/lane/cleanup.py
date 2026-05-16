from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from lane.forge_remote import (
    ForgeRemoteError,
    infer_forge_remote,
    parse_gitlab_mr_url,
    provider_from_pr_url,
)
from lane.state import LaneState


class CleanupError(RuntimeError):
    pass


class Runner(Protocol):
    def __call__(
        self,
        argv: list[str],
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        pass


def write_cleanup_archive_summary(
    root: Path,
    state: LaneState,
    *,
    merge_status: str,
    archive_status: str,
    removed_agents: tuple[str, ...] = (),
) -> Path:
    path = root / ".lane" / "archive" / f"{_safe_filename(state.id)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = {
        "schema": 1,
        "written_at": datetime.now(UTC).isoformat(),
        "lane": {
            "id": state.id,
            "branch": state.branch,
            "base": state.base,
            "path": str(state.path),
            "status": state.status,
            "review": state.review,
            "pr": state.pr,
        },
        "archived_spec": state.spec,
        "merge_status": merge_status,
        "archive": {
            "status": archive_status,
            "removed_agents": list(removed_agents),
        },
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(raw, handle, indent=2)
        handle.write("\n")
    return path


def cleanup_archive_root(invocation: Path, workspace: Path) -> Path:
    invocation = invocation.resolve()
    workspace = workspace.resolve()
    if invocation == workspace or workspace in invocation.parents:
        return workspace.parent
    return invocation


def ensure_clean_worktree(
    workspace: Path,
    *,
    allow_dirty: bool = False,
    runner: Runner | None = None,
) -> None:
    if allow_dirty:
        return
    runner = _run if runner is None else runner
    result = _run_required(["git", "status", "--porcelain"], workspace, runner)
    if result.stdout.strip():
        raise CleanupError("worktree has uncommitted changes; pass --discard to abort")


def ensure_pr_merged(
    pr_url: str | None,
    workspace: Path,
    *,
    runner: Runner | None = None,
) -> None:
    if pr_url is None:
        raise CleanupError("cleanup requires a PR URL to verify merge status")
    try:
        provider = provider_from_pr_url(pr_url)
    except ForgeRemoteError as error:
        raise CleanupError(str(error)) from error
    cli = _forge_cli(provider)
    _require_tool(cli, purpose=_forge_purpose(provider, "merge verification"))
    runner = _run if runner is None else runner
    if provider == "github":
        result = _run_required(
            ["gh", "pr", "view", pr_url, "--json", "mergedAt", "--jq", ".mergedAt"],
            workspace,
            runner,
        )
        merged = result.stdout.strip() != ""
    else:
        mr = _gitlab_mr(pr_url)
        result = _run_required(
            [
                "glab",
                "mr",
                "view",
                mr.iid,
                "--repo",
                mr.repo_selector,
                "--output",
                "json",
            ],
            workspace,
            runner,
        )
        merged = _gitlab_mr_is_merged(result.stdout)
    if not merged:
        raise CleanupError("PR is not merged; refusing cleanup")


def close_pr(
    pr_url: str | None,
    workspace: Path,
    *,
    runner: Runner | None = None,
) -> None:
    if pr_url is None:
        return
    try:
        provider = provider_from_pr_url(pr_url)
    except ForgeRemoteError as error:
        raise CleanupError(str(error)) from error
    cli = _forge_cli(provider)
    _require_tool(cli, purpose=_forge_purpose(provider, "close"))
    runner = _run if runner is None else runner
    if provider == "github":
        _run_required(["gh", "pr", "close", pr_url], workspace, runner)
    else:
        mr = _gitlab_mr(pr_url)
        _run_required(
            ["glab", "mr", "close", mr.iid, "--repo", mr.repo_selector],
            workspace,
            runner,
        )


def delete_remote_branch(
    branch: str,
    workspace: Path,
    *,
    runner: Runner | None = None,
) -> None:
    _require_tool("git")
    runner = _run if runner is None else runner
    try:
        remote = infer_forge_remote(workspace, runner=runner)
    except ForgeRemoteError as error:
        raise CleanupError(str(error)) from error
    _run_required(["git", "push", remote.name, "--delete", branch], workspace, runner)


def _run_required(
    argv: list[str],
    cwd: Path,
    runner: Runner,
) -> subprocess.CompletedProcess[str]:
    result = runner(argv, cwd)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise CleanupError(f"{' '.join(argv[:3])} failed: {message}")
    return result


def _forge_cli(provider: str) -> str:
    return "gh" if provider == "github" else "glab"


def _forge_purpose(provider: str, action: str) -> str:
    label = "GitHub PR" if provider == "github" else "GitLab MR"
    return f"{label} {action}"


def _gitlab_mr_is_merged(output: str) -> bool:
    try:
        raw = json.loads(output)
    except json.JSONDecodeError:
        return False
    state = raw.get("state")
    return isinstance(state, str) and state.lower() == "merged"


def _gitlab_mr(pr_url: str):
    try:
        return parse_gitlab_mr_url(pr_url)
    except ForgeRemoteError as error:
        raise CleanupError(str(error)) from error


def _safe_filename(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "._-" else "-"
        for character in value
    )


def _require_tool(tool: str, *, purpose: str | None = None) -> None:
    if shutil.which(tool) is None:
        requirement = f"{purpose} requires" if purpose is not None else "required"
        raise CleanupError(f"{requirement} `{tool}` on PATH")


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
