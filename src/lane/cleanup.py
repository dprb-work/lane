from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Protocol


class CleanupError(RuntimeError):
    pass


class Runner(Protocol):
    def __call__(
        self,
        argv: list[str],
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        pass


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
    _require_tool("gh")
    runner = _run if runner is None else runner
    result = _run_required(
        ["gh", "pr", "view", pr_url, "--json", "mergedAt", "--jq", ".mergedAt"],
        workspace,
        runner,
    )
    if result.stdout.strip() == "":
        raise CleanupError("PR is not merged; refusing cleanup")


def close_pr(
    pr_url: str | None,
    workspace: Path,
    *,
    runner: Runner | None = None,
) -> None:
    if pr_url is None:
        return
    _require_tool("gh")
    runner = _run if runner is None else runner
    _run_required(["gh", "pr", "close", pr_url], workspace, runner)


def delete_remote_branch(
    branch: str,
    workspace: Path,
    *,
    runner: Runner | None = None,
) -> None:
    _require_tool("git")
    runner = _run if runner is None else runner
    _run_required(["git", "push", "origin", "--delete", branch], workspace, runner)


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


def _require_tool(tool: str) -> None:
    if shutil.which(tool) is None:
        raise CleanupError(f"required cleanup executable not found on PATH: {tool}")


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
