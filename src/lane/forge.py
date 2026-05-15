from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from lane.forge_remote import ForgeRemote, ForgeRemoteError, infer_forge_remote
from lane.github_remote import GitHubRemoteError, infer_github_remote
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
    try:
        return infer_github_remote(cwd, runner=runner).repo
    except GitHubRemoteError as error:
        raise ForgeError(str(error)) from error


def finalize_pr(
    state: LaneState,
    verification: VerifyResult,
    *,
    runner: Runner | None = None,
) -> ForgeResult:
    runner = _run if runner is None else runner
    try:
        remote = infer_forge_remote(state.path, runner=runner)
    except ForgeRemoteError as error:
        raise ForgeError(str(error)) from error
    if remote.provider == "github":
        _require_tool("gh", purpose="GitHub PR finalization")
        return _finalize_github_pr(state, verification, remote, runner)
    if remote.provider == "gitlab":
        _require_tool("glab", purpose="GitLab MR finalization")
        return _finalize_gitlab_mr(state, verification, remote, runner)
    raise ForgeError(f"unsupported forge provider: {remote.provider}")


def _finalize_github_pr(
    state: LaneState,
    verification: VerifyResult,
    remote: ForgeRemote,
    runner: Runner,
) -> ForgeResult:
    repo = remote.repo

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


def _finalize_gitlab_mr(
    state: LaneState,
    verification: VerifyResult,
    remote: ForgeRemote,
    runner: Runner,
) -> ForgeResult:
    repo = remote.repo

    title = _pr_title(state.branch, state.id)
    body = pr_body(state, verification)
    existing = _existing_mr_url(state.branch, state.path, runner)
    if existing is None:
        create = _run_required(
            [
                "glab",
                "mr",
                "create",
                "--title",
                title,
                "--description",
                body,
                "--target-branch",
                state.base,
                "--source-branch",
                state.branch,
                "--yes",
            ],
            state.path,
            runner,
        )
        mr_url = _extract_url(create.stdout)
    else:
        _run_required(
            [
                "glab",
                "mr",
                "update",
                state.branch,
                "--title",
                title,
                "--description",
                body,
                "--yes",
            ],
            state.path,
            runner,
        )
        mr_url = existing

    if mr_url == "":
        raise ForgeError("glab did not return an MR URL")
    return ForgeResult(repo=repo, pr_url=mr_url)


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


def _existing_pr_url(branch: str, cwd: Path, runner: Runner) -> str | None:
    result = runner(["gh", "pr", "view", branch, "--json", "url", "--jq", ".url"], cwd)
    if result.returncode != 0:
        return None
    url = result.stdout.strip()
    return url or None


def _existing_mr_url(branch: str, cwd: Path, runner: Runner) -> str | None:
    result = runner(["glab", "mr", "view", branch, "--output", "json"], cwd)
    if result.returncode != 0:
        return None
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    url = raw.get("web_url") or raw.get("webUrl") or raw.get("url")
    return url if isinstance(url, str) and url else None


def _extract_url(output: str) -> str:
    for token in output.split():
        if token.startswith("http://") or token.startswith("https://"):
            return token.rstrip(".,")
    return output.strip()


def push_branch(
    state: LaneState,
    *,
    force_with_lease: bool = False,
    runner: Runner | None = None,
) -> str:
    _require_tool("git")
    runner = _run if runner is None else runner
    try:
        remote = infer_forge_remote(state.path, runner=runner)
    except ForgeRemoteError as error:
        raise ForgeError(str(error)) from error
    argv = ["git", "push"]
    if force_with_lease:
        argv.append("--force-with-lease")
    argv.extend(["-u", remote.name, state.branch])
    _run_required(argv, state.path, runner)
    return remote.repo


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


def _require_tool(tool: str, *, purpose: str | None = None) -> None:
    if shutil.which(tool) is None:
        requirement = f"{purpose} requires" if purpose is not None else "required"
        raise ForgeError(f"{requirement} `{tool}` on PATH")


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
