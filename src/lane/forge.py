from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import quote, urlparse

from lane.forge_remote import (
    ForgeRemote,
    ForgeRemoteError,
    infer_forge_remote,
    parse_gitlab_mr_url,
    provider_from_pr_url,
)
from lane.github_remote import GitHubRemoteError, infer_github_remote
from lane.review import ReviewResult
from lane.state import LaneState
from lane.verify import VerifyResult


class ForgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class ForgeResult:
    repo: str
    pr_url: str


REVIEW_SUMMARY_MARKER = "<!-- lane-review-summary -->"


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


def create_draft_pr(
    state: LaneState,
    *,
    runner: Runner | None = None,
) -> ForgeResult:
    runner = _run if runner is None else runner
    try:
        remote = infer_forge_remote(state.path, runner=runner)
    except ForgeRemoteError as error:
        raise ForgeError(str(error)) from error
    if remote.provider == "github":
        _require_tool("gh", purpose="GitHub draft PR creation")
        return _create_github_pr(state, None, remote, runner, draft=True)
    if remote.provider == "gitlab":
        _require_tool("glab", purpose="GitLab draft MR creation")
        return _create_gitlab_mr(state, None, remote, runner, draft=True)
    raise ForgeError(f"unsupported forge provider: {remote.provider}")


def update_pr_metadata(
    state: LaneState,
    verification: VerifyResult | None = None,
    *,
    runner: Runner | None = None,
) -> str | None:
    if state.pr is None:
        return None
    runner = _run if runner is None else runner
    try:
        provider = provider_from_pr_url(state.pr)
    except ForgeRemoteError as error:
        raise ForgeError(str(error)) from error
    title = _pr_title(state.branch, state.id)
    body = pr_body(state, verification)
    if provider == "github":
        _require_tool("gh", purpose="GitHub PR metadata update")
        _run_required(
            ["gh", "pr", "edit", state.pr, "--title", title, "--body", body],
            state.path,
            runner,
        )
    else:
        _require_tool("glab", purpose="GitLab MR metadata update")
        mr = _gitlab_mr(state.pr)
        title = _preserve_gitlab_draft_prefix(
            title,
            mr.iid,
            mr.repo_selector,
            state.path,
            runner,
        )
        _run_required(
            [
                "glab",
                "mr",
                "update",
                mr.iid,
                "--repo",
                mr.repo_selector,
                "--title",
                title,
                "--description",
                body,
                "--yes",
            ],
            state.path,
            runner,
        )
    return state.pr


def post_or_update_review_summary_comment(
    state: LaneState,
    result: ReviewResult,
    *,
    runner: Runner | None = None,
) -> str | None:
    if state.pr is None:
        return None
    runner = _run if runner is None else runner
    body = review_summary_comment_body(state, result)
    try:
        provider = provider_from_pr_url(state.pr)
    except ForgeRemoteError as error:
        raise ForgeError(str(error)) from error
    if provider == "github":
        _require_tool("gh", purpose="GitHub PR review comment update")
        return _post_or_update_github_review_comment(state.pr, body, state.path, runner)

    _require_tool("glab", purpose="GitLab MR review comment update")
    return _post_gitlab_review_comment(state.pr, body, state.path, runner)


def review_summary_comment_body(state: LaneState, result: ReviewResult) -> str:
    missing = ", ".join(f"`{agent}`" for agent in result.missing_agents) or "none"
    runs = [
        "| Agent | Paseo agent | Exit status |",
        "| --- | --- | --- |",
    ]
    runs.extend(
        f"| `{run.agent}` | `{run.paseo_agent_id or 'unknown'}` | `{run.exit_status}` |"
        for run in result.runs
    )
    if not result.runs:
        runs.append("| none | none | `0` |")
    return "\n".join(
        [
            REVIEW_SUMMARY_MARKER,
            "## Lane Review Summary",
            f"- Lane: `{state.id}`.",
            f"- Branch: `{state.branch}`.",
            f"- Reviewed head: `{state.review_head or 'unknown'}`.",
            f"- Aggregate review: `{result.review}`.",
            f"- Missing agents: {missing}.",
            "",
            "## Runs",
            *runs,
        ]
    )


def mark_pr_ready(
    pr_url: str,
    workspace: Path,
    *,
    runner: Runner | None = None,
) -> None:
    runner = _run if runner is None else runner
    try:
        provider = provider_from_pr_url(pr_url)
    except ForgeRemoteError as error:
        raise ForgeError(str(error)) from error
    if provider == "github":
        _require_tool("gh", purpose="GitHub PR ready transition")
        _run_required(["gh", "pr", "ready", pr_url], workspace, runner)
    else:
        _require_tool("glab", purpose="GitLab MR ready transition")
        mr = _gitlab_mr(pr_url)
        _run_required(
            ["glab", "mr", "update", mr.iid, "--repo", mr.repo_selector, "--ready"],
            workspace,
            runner,
        )


@dataclass(frozen=True)
class _GitHubPullRequest:
    repo: str
    number: str


def _post_or_update_github_review_comment(
    pr_url: str,
    body: str,
    workspace: Path,
    runner: Runner,
) -> str | None:
    pr = _parse_github_pr_url(pr_url)
    comments_path = f"repos/{pr.repo}/issues/{pr.number}/comments"
    existing = _existing_github_review_comment(comments_path, workspace, runner)
    if existing is not None:
        update = _run_required(
            [
                "gh",
                "api",
                f"repos/{pr.repo}/issues/comments/{existing}",
                "-X",
                "PATCH",
                "-f",
                f"body={body}",
            ],
            workspace,
            runner,
        )
        return _comment_url_from_json(update.stdout)
    create = _run_required(
        ["gh", "pr", "comment", pr_url, "--body", body],
        workspace,
        runner,
    )
    return create.stdout.strip() or None


def _existing_github_review_comment(
    comments_path: str,
    workspace: Path,
    runner: Runner,
) -> str | None:
    result = _run_required(
        ["gh", "api", comments_path, "--paginate", "--slurp"],
        workspace,
        runner,
    )
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    for comment in _flatten_comments(raw):
        if not isinstance(comment, dict):
            continue
        body = comment.get("body")
        comment_id = comment.get("id")
        if isinstance(body, str) and REVIEW_SUMMARY_MARKER in body:
            return str(comment_id) if comment_id is not None else None
    return None


def _flatten_comments(raw: object) -> list[object]:
    if not isinstance(raw, list):
        return []
    comments: list[object] = []
    for item in raw:
        if isinstance(item, list):
            comments.extend(item)
        else:
            comments.append(item)
    return comments


def _comment_url_from_json(output: str) -> str | None:
    try:
        raw = json.loads(output)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    url = raw.get("html_url") or raw.get("web_url") or raw.get("url")
    return url if isinstance(url, str) and url else None


def _post_gitlab_review_comment(
    mr_url: str,
    body: str,
    workspace: Path,
    runner: Runner,
) -> str | None:
    mr = _gitlab_mr(mr_url)
    notes_path = _gitlab_notes_path(mr.repo_selector, mr.iid)
    api_hostname = _gitlab_api_hostname(mr.repo_selector)
    existing = _existing_gitlab_review_note(notes_path, api_hostname, workspace, runner)
    if existing is not None:
        argv = [
            "glab",
            "api",
            f"{notes_path}/{existing}",
            "-X",
            "PUT",
            "-f",
            f"body={body}",
        ]
        if api_hostname is not None:
            argv.extend(["--hostname", api_hostname])
        update = _run_required(
            argv,
            workspace,
            runner,
        )
        return _comment_url_from_json(update.stdout)
    create = _run_required(
        [
            "glab",
            "mr",
            "note",
            mr.iid,
            "--repo",
            mr.repo_selector,
            "--message",
            body,
        ],
        workspace,
        runner,
    )
    url = _extract_url(create.stdout)
    return url or None


def _existing_gitlab_review_note(
    notes_path: str,
    api_hostname: str | None,
    workspace: Path,
    runner: Runner,
) -> str | None:
    argv = ["glab", "api", notes_path, "--paginate"]
    if api_hostname is not None:
        argv.extend(["--hostname", api_hostname])
    result = _run_required(
        argv,
        workspace,
        runner,
    )
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    for note in _flatten_comments(raw):
        if not isinstance(note, dict):
            continue
        body = note.get("body")
        note_id = note.get("id")
        if isinstance(body, str) and REVIEW_SUMMARY_MARKER in body:
            return str(note_id) if note_id is not None else None
    return None


def _gitlab_notes_path(repo_selector: str, iid: str) -> str:
    parsed = urlparse(repo_selector)
    repo = parsed.path.strip("/") if parsed.scheme else repo_selector.strip("/")
    return f"projects/{quote(repo, safe='')}/merge_requests/{iid}/notes"


def _gitlab_api_hostname(repo_selector: str) -> str | None:
    parsed = urlparse(repo_selector)
    if not parsed.scheme or not parsed.netloc:
        return None
    hostname = parsed.netloc.rsplit("@", maxsplit=1)[-1]
    return None if hostname == "gitlab.com" else hostname


def _parse_github_pr_url(pr_url: str) -> _GitHubPullRequest:
    parsed = urlparse(pr_url)
    parts = parsed.path.strip("/").split("/")
    if parsed.hostname != "github.com" or len(parts) != 4 or parts[2] != "pull":
        raise ForgeError(f"not a GitHub PR URL: {pr_url}")
    return _GitHubPullRequest(repo=f"{parts[0]}/{parts[1]}", number=parts[3])


def _finalize_github_pr(
    state: LaneState,
    verification: VerifyResult,
    remote: ForgeRemote,
    runner: Runner,
) -> ForgeResult:
    repo = remote.repo

    existing = _existing_pr_url(state.branch, state.path, runner)
    if existing is None:
        return _create_github_pr(state, verification, remote, runner, draft=False)
    else:
        update_pr_metadata(_state_with_pr(state, existing), verification, runner=runner)
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

    existing = _existing_mr_url(state.branch, state.path, runner)
    if existing is None:
        return _create_gitlab_mr(state, verification, remote, runner, draft=False)
    else:
        update_pr_metadata(_state_with_pr(state, existing), verification, runner=runner)
        mr_url = existing

    if mr_url == "":
        raise ForgeError("glab did not return an MR URL")
    return ForgeResult(repo=repo, pr_url=mr_url)


def pr_body(state: LaneState, verification: VerifyResult | None = None) -> str:
    verification_line = (
        "- Not verified yet."
        if verification is None
        else f"- `{verification.command.label}` exited {verification.exit_status}."
    )
    return "\n".join(
        [
            "## Summary",
            f"- Lane `{state.id}` for branch `{state.branch}`.",
            "",
            "## Verification",
            verification_line,
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


def _create_github_pr(
    state: LaneState,
    verification: VerifyResult | None,
    remote: ForgeRemote,
    runner: Runner,
    *,
    draft: bool,
) -> ForgeResult:
    argv = [
        "gh",
        "pr",
        "create",
        "--title",
        _pr_title(state.branch, state.id),
        "--body",
        pr_body(state, verification),
        "--base",
        state.base,
        "--head",
        state.branch,
    ]
    if draft:
        argv.append("--draft")
    create = _run_required(argv, state.path, runner)
    pr_url = create.stdout.strip()
    if pr_url == "":
        raise ForgeError("gh did not return a PR URL")
    return ForgeResult(repo=remote.repo, pr_url=pr_url)


def _create_gitlab_mr(
    state: LaneState,
    verification: VerifyResult | None,
    remote: ForgeRemote,
    runner: Runner,
    *,
    draft: bool,
) -> ForgeResult:
    title = _pr_title(state.branch, state.id)
    if draft:
        title = f"Draft: {title}"
    create = _run_required(
        [
            "glab",
            "mr",
            "create",
            "--title",
            title,
            "--description",
            pr_body(state, verification),
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
    if mr_url == "":
        raise ForgeError("glab did not return an MR URL")
    return ForgeResult(repo=remote.repo, pr_url=mr_url)


def _state_with_pr(state: LaneState, pr_url: str) -> LaneState:
    return LaneState(
        schema=state.schema,
        id=state.id,
        status=state.status,
        branch=state.branch,
        base=state.base,
        path=state.path,
        spec=state.spec,
        review=state.review,
        review_head=state.review_head,
        pr=pr_url,
        verification=state.verification,
    )


def _gitlab_mr(pr_url: str):
    try:
        return parse_gitlab_mr_url(pr_url)
    except ForgeRemoteError as error:
        raise ForgeError(str(error)) from error


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


def _preserve_gitlab_draft_prefix(
    title: str,
    iid: str,
    repo_selector: str,
    cwd: Path,
    runner: Runner,
) -> str:
    existing = _gitlab_mr_title(iid, repo_selector, cwd, runner)
    if existing is None:
        return title
    for prefix in ("Draft:", "WIP:"):
        if existing.lower().startswith(prefix.lower()):
            return f"{prefix} {title}"
    return title


def _gitlab_mr_title(
    iid: str,
    repo_selector: str,
    cwd: Path,
    runner: Runner,
) -> str | None:
    result = runner(
        ["glab", "mr", "view", iid, "--repo", repo_selector, "--output", "json"],
        cwd,
    )
    if result.returncode != 0:
        return None
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    title = raw.get("title")
    return title if isinstance(title, str) else None


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
