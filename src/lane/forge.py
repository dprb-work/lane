from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from lane.state import LaneState
from lane.verify import VerifyResult


class ForgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class ForgeResult:
    repo: str
    pr_url: str


class Runner(Protocol):
    def __call__(
        self,
        argv: list[str],
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        pass


def infer_github_repo(cwd: Path, *, runner: Runner | None = None) -> str:
    runner = _run if runner is None else runner
    result = runner(["git", "remote", "get-url", "origin"], cwd)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "origin not found"
        raise ForgeError(f"failed to infer GitHub repo: {message}")
    return _parse_github_remote(result.stdout.strip())


def finalize_pr(
    state: LaneState,
    verification: VerifyResult,
    *,
    runner: Runner | None = None,
) -> ForgeResult:
    _require_tool("git")
    _require_tool("gh")
    runner = _run if runner is None else runner
    repo = infer_github_repo(state.path, runner=runner)
    _run_required(["git", "push", "-u", "origin", state.branch], state.path, runner)

    title = _pr_title(state.branch, state.id)
    body = pr_body(state, verification)
    existing = _existing_pr_url(state.branch, state.path, runner)
    if existing is None:
        create = _run_required(
            [
                "gh",
                "pr",
                "create",
                "--title",
                title,
                "--body",
                body,
                "--base",
                state.base,
                "--head",
                state.branch,
            ],
            state.path,
            runner,
        )
        pr_url = create.stdout.strip()
    else:
        _run_required(
            ["gh", "pr", "edit", state.branch, "--title", title, "--body", body],
            state.path,
            runner,
        )
        pr_url = existing

    if pr_url == "":
        raise ForgeError("gh did not return a PR URL")
    return ForgeResult(repo=repo, pr_url=pr_url)


def pr_body(state: LaneState, verification: VerifyResult) -> str:
    return "\n".join(
        [
            "## Summary",
            f"- Lane `{state.id}` for branch `{state.branch}`.",
            "",
            "## Verification",
            f"- `{verification.command.label}` exited {verification.exit_status}.",
            "",
            "## Review",
            f"- Aggregate review: `{state.review}`.",
            "",
            "## Spec",
            f"- `{state.spec}` archived/synced before finalize.",
            "",
            "## Lane",
            f"- `{state.path}`",
        ]
    )


def _parse_github_remote(remote: str) -> str:
    ssh_match = re.fullmatch(
        r"git@github\.com:(?P<repo>[^/]+/[^/]+?)(?:\.git)?",
        remote,
    )
    if ssh_match is not None:
        return ssh_match.group("repo")

    parsed = urlparse(remote)
    if parsed.hostname != "github.com":
        raise ForgeError(f"origin is not a GitHub remote: {remote}")
    repo = parsed.path.strip("/")
    if repo.endswith(".git"):
        repo = repo[:-4]
    if repo.count("/") != 1:
        raise ForgeError(f"cannot parse GitHub repo from origin: {remote}")
    return repo


def _existing_pr_url(branch: str, cwd: Path, runner: Runner) -> str | None:
    result = runner(["gh", "pr", "view", branch, "--json", "url", "--jq", ".url"], cwd)
    if result.returncode != 0:
        return None
    url = result.stdout.strip()
    return url or None


def _pr_title(branch: str, lane_id: str) -> str:
    branch_type = branch.split("/", maxsplit=1)[0]
    return f"{branch_type}: {lane_id.replace('-', ' ')}"


def _run_required(
    argv: list[str],
    cwd: Path,
    runner: Runner,
) -> subprocess.CompletedProcess[str]:
    result = runner(argv, cwd)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise ForgeError(f"{' '.join(argv[:3])} failed: {message}")
    return result


def _require_tool(tool: str) -> None:
    if shutil.which(tool) is None:
        raise ForgeError(f"required forge executable not found on PATH: {tool}")


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
