from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lane.forge import (
    ForgeError,
    create_draft_pr,
    finalize_pr,
    infer_github_repo,
    mark_pr_ready,
    post_or_update_review_summary_comment,
    pr_body,
    push_branch,
    review_summary_comment_body,
    update_pr_metadata,
)
from lane.forge_remote import infer_forge_remote, parse_forge_remote_url
from lane.review import ReviewResult, ReviewRun
from lane.state import LaneState
from lane.verify import VerifyCommand, VerifyResult


def test_infer_github_repo_from_https_remote() -> None:
    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return _result("upstream\thttps://github.com/acme/app.git (fetch)\n")

    assert infer_github_repo(Path("/repo"), runner=runner) == "acme/app"


def test_infer_github_repo_from_ssh_remote() -> None:
    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return _result("upstream\tgit@github.com:acme/app.git (fetch)\n")

    assert infer_github_repo(Path("/repo"), runner=runner) == "acme/app"


def test_infer_github_repo_rejects_non_github_remote() -> None:
    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return _result("origin\thttps://gitlab.com/acme/app.git (fetch)\n")

    with pytest.raises(ForgeError, match="no GitHub remote"):
        infer_github_repo(Path("/repo"), runner=runner)


def test_infer_github_repo_skips_non_github_remote() -> None:
    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return _result(
            "origin\thttps://gitlab.com/acme/app.git (fetch)\n"
            "upstream\thttps://github.com/acme/app.git (fetch)\n"
        )

    assert infer_github_repo(Path("/repo"), runner=runner) == "acme/app"


def test_infer_forge_remote_detects_gitlab_remote() -> None:
    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return _result("origin\thttps://gitlab.com/acme/group/app.git (fetch)\n")

    remote = infer_forge_remote(Path("/repo"), runner=runner)

    assert remote.provider == "gitlab"
    assert remote.name == "origin"
    assert remote.host == "gitlab.com"
    assert remote.repo == "acme/group/app"


def test_parse_forge_remote_url_detects_gitlab_ssh_remote() -> None:
    assert parse_forge_remote_url("git@gitlab.com:acme/group/app.git") == (
        "gitlab",
        "acme/group/app",
    )


def test_parse_forge_remote_url_detects_self_hosted_gitlab_remote() -> None:
    assert parse_forge_remote_url("git@git.example.test:acme/group/app.git") == (
        "gitlab",
        "acme/group/app",
    )


def test_infer_forge_remote_preserves_https_port() -> None:
    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return _result(
            "origin\thttps://gitlab.example.com:8443/acme/group/app.git (fetch)\n"
        )

    remote = infer_forge_remote(Path("/repo"), runner=runner)

    assert remote.host == "gitlab.example.com:8443"


def test_finalize_pr_creates_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lane.forge.shutil.which", lambda _: "/usr/bin/tool")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv == ["git", "remote", "-v"]:
            return _result("upstream\thttps://github.com/acme/app.git (fetch)\n")
        if argv[:4] == ["gh", "pr", "view", "fix/login"]:
            return _result("", returncode=1)
        if argv[:3] == ["gh", "pr", "create"]:
            return _result("https://github.com/acme/app/pull/123\n")
        return _result("")

    result = finalize_pr(_state(), _verification(), runner=runner)

    assert result.pr_url == "https://github.com/acme/app/pull/123"
    assert any(call[:3] == ["gh", "pr", "create"] for call in calls)
    assert not any("--draft" in call for call in calls)


def test_create_draft_pr_uses_github_draft_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.forge.shutil.which", lambda _: "/usr/bin/tool")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv == ["git", "remote", "-v"]:
            return _result("upstream\thttps://github.com/acme/app.git (fetch)\n")
        if argv[:3] == ["gh", "pr", "create"]:
            return _result("https://github.com/acme/app/pull/123\n")
        return _result("")

    result = create_draft_pr(_state(), runner=runner)

    assert result.pr_url == "https://github.com/acme/app/pull/123"
    create = next(call for call in calls if call[:3] == ["gh", "pr", "create"])
    assert "--draft" in create
    assert any("Not verified yet" in argument for argument in create)


def test_finalize_pr_updates_existing_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lane.forge.shutil.which", lambda _: "/usr/bin/tool")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv == ["git", "remote", "-v"]:
            return _result("upstream\thttps://github.com/acme/app.git (fetch)\n")
        if argv[:4] == ["gh", "pr", "view", "fix/login"]:
            return _result("https://github.com/acme/app/pull/123\n")
        return _result("")

    result = finalize_pr(_state(), _verification(), runner=runner)

    assert result.pr_url == "https://github.com/acme/app/pull/123"
    assert any(call[:3] == ["gh", "pr", "edit"] for call in calls)


def test_update_pr_metadata_edits_known_github_pr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.forge.shutil.which", lambda _: "/usr/bin/tool")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return _result("")

    state = _state(pr="https://github.com/acme/app/pull/123")

    assert update_pr_metadata(state, _verification(), runner=runner) == state.pr
    assert calls == [
        [
            "gh",
            "pr",
            "edit",
            "https://github.com/acme/app/pull/123",
            "--title",
            "fix: login",
            "--body",
            pr_body(state, _verification()),
        ]
    ]


def test_finalize_pr_creates_gitlab_mr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lane.forge.shutil.which", lambda _: "/usr/bin/tool")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv == ["git", "remote", "-v"]:
            return _result("origin\thttps://gitlab.com/acme/app.git (fetch)\n")
        if argv[:4] == ["glab", "mr", "view", "fix/login"]:
            return _result("", returncode=1)
        if argv[:3] == ["glab", "mr", "create"]:
            return _result("Created https://gitlab.com/acme/app/-/merge_requests/123\n")
        return _result("")

    result = finalize_pr(_state(), _verification(), runner=runner)

    assert result.pr_url == "https://gitlab.com/acme/app/-/merge_requests/123"
    assert any(call[:3] == ["glab", "mr", "create"] for call in calls)


def test_create_draft_pr_prefixes_gitlab_draft_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.forge.shutil.which", lambda _: "/usr/bin/tool")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv == ["git", "remote", "-v"]:
            return _result("origin\thttps://gitlab.com/acme/app.git (fetch)\n")
        if argv[:3] == ["glab", "mr", "create"]:
            return _result("Created https://gitlab.com/acme/app/-/merge_requests/123\n")
        return _result("")

    result = create_draft_pr(_state(), runner=runner)

    assert result.pr_url == "https://gitlab.com/acme/app/-/merge_requests/123"
    create = next(call for call in calls if call[:3] == ["glab", "mr", "create"])
    assert create[create.index("--title") + 1] == "Draft: fix: login"


def test_push_branch_pushes_to_inferred_remote(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lane.forge.shutil.which", lambda _: "/usr/bin/tool")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv == ["git", "remote", "-v"]:
            return _result("upstream\thttps://github.com/acme/app.git (fetch)\n")
        return _result("")

    repo = push_branch(_state(), runner=runner)

    assert repo == "acme/app"
    assert ["git", "push", "-u", "upstream", "fix/login"] in calls


def test_push_branch_supports_force_with_lease(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lane.forge.shutil.which", lambda _: "/usr/bin/tool")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv == ["git", "remote", "-v"]:
            return _result("upstream\thttps://github.com/acme/app.git (fetch)\n")
        return _result("")

    push_branch(_state(), force_with_lease=True, runner=runner)

    assert [
        "git",
        "push",
        "--force-with-lease",
        "-u",
        "upstream",
        "fix/login",
    ] in calls


def test_finalize_pr_updates_existing_gitlab_mr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.forge.shutil.which", lambda _: "/usr/bin/tool")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv == ["git", "remote", "-v"]:
            return _result("origin\thttps://gitlab.com/acme/app.git (fetch)\n")
        if argv[:4] == ["glab", "mr", "view", "fix/login"]:
            return _result('{"web_url":"https://gitlab.com/acme/app/-/merge_requests/123"}\n')
        return _result("")

    result = finalize_pr(_state(), _verification(), runner=runner)

    assert result.pr_url == "https://gitlab.com/acme/app/-/merge_requests/123"
    assert any(call[:3] == ["glab", "mr", "update"] for call in calls)


def test_update_pr_metadata_preserves_gitlab_draft_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.forge.shutil.which", lambda _: "/usr/bin/tool")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[:4] == ["glab", "mr", "view", "123"]:
            return _result('{"title":"Draft: old title"}\n')
        return _result("")

    state = _state(pr="https://gitlab.com/acme/app/-/merge_requests/123")

    update_pr_metadata(state, _verification(), runner=runner)

    update = next(call for call in calls if call[:3] == ["glab", "mr", "update"])
    assert update[update.index("--title") + 1] == "Draft: fix: login"


def test_mark_pr_ready_calls_github_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lane.forge.shutil.which", lambda _: "/usr/bin/tool")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return _result("")

    mark_pr_ready("https://github.com/acme/app/pull/123", Path("/repo"), runner=runner)

    assert calls == [["gh", "pr", "ready", "https://github.com/acme/app/pull/123"]]


def test_finalize_pr_requires_only_detected_forge_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_which(tool: str) -> str | None:
        return "/usr/bin/git" if tool == "git" else None

    monkeypatch.setattr("lane.forge.shutil.which", fake_which)

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv == ["git", "remote", "-v"]:
            return _result("origin\thttps://gitlab.com/acme/app.git (fetch)\n")
        return _result("")

    with pytest.raises(ForgeError, match="GitLab MR finalization requires `glab`"):
        finalize_pr(_state(), _verification(), runner=runner)


def test_pr_body_records_verification_review_spec_and_lane() -> None:
    body = pr_body(_state(), _verification())

    assert "`just verify` exited 0" in body
    assert "Aggregate review: `approve`" in body
    assert "`login` archived/synced" in body
    assert "`/workspace`" in body


def test_review_summary_comment_body_records_review_runs() -> None:
    body = review_summary_comment_body(_state(review_head="abc123"), _review_result())

    assert "<!-- lane-review-summary -->" in body
    assert "Aggregate review: `approve`" in body
    assert "Reviewed head: `abc123`" in body
    assert "`lane-review-quality`" in body
    assert "`agent-1`" in body


def test_post_review_summary_creates_github_comment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.forge.shutil.which", lambda _: "/usr/bin/tool")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[:2] == ["gh", "api"]:
            return _result("[]")
        return _result("https://github.com/acme/app/pull/123#issuecomment-1\n")

    state = _state(pr="https://github.com/acme/app/pull/123")

    assert (
        post_or_update_review_summary_comment(state, _review_result(), runner=runner)
        == "https://github.com/acme/app/pull/123#issuecomment-1"
    )
    assert calls[0] == [
        "gh",
        "api",
        "repos/acme/app/issues/123/comments",
        "--paginate",
        "--slurp",
    ]
    assert calls[1][:4] == [
        "gh",
        "pr",
        "comment",
        "https://github.com/acme/app/pull/123",
    ]
    assert any("<!-- lane-review-summary -->" in argument for argument in calls[1])


def test_post_review_summary_updates_existing_github_comment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.forge.shutil.which", lambda _: "/usr/bin/tool")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv == [
            "gh",
            "api",
            "repos/acme/app/issues/123/comments",
            "--paginate",
            "--slurp",
        ]:
            return _result('[[{"id":456,"body":"<!-- lane-review-summary --> old"}]]')
        return _result('{"html_url":"https://github.com/acme/app/pull/123#issuecomment-456"}')

    state = _state(pr="https://github.com/acme/app/pull/123")

    assert (
        post_or_update_review_summary_comment(state, _review_result(), runner=runner)
        == "https://github.com/acme/app/pull/123#issuecomment-456"
    )
    assert calls[1][:3] == ["gh", "api", "repos/acme/app/issues/comments/456"]
    assert "PATCH" in calls[1]


def test_post_review_summary_posts_gitlab_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.forge.shutil.which", lambda _: "/usr/bin/tool")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[:2] == ["glab", "api"]:
            return _result("[]")
        return _result("Created https://gitlab.com/acme/app/-/merge_requests/123#note_1\n")

    state = _state(pr="https://gitlab.com/acme/app/-/merge_requests/123")

    assert (
        post_or_update_review_summary_comment(state, _review_result(), runner=runner)
        == "https://gitlab.com/acme/app/-/merge_requests/123#note_1"
    )
    assert calls == [
        [
            "glab",
            "api",
            "projects/acme%2Fapp/merge_requests/123/notes",
            "--paginate",
        ],
        [
            "glab",
            "mr",
            "note",
            "123",
            "--repo",
            "https://gitlab.com/acme/app",
            "--message",
            review_summary_comment_body(state, _review_result()),
        ]
    ]


def test_post_review_summary_updates_existing_gitlab_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lane.forge.shutil.which", lambda _: "/usr/bin/tool")
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv == [
            "glab",
            "api",
            "projects/acme%2Fapp/merge_requests/123/notes",
            "--paginate",
        ]:
            return _result('[{"id":789,"body":"<!-- lane-review-summary --> old"}]')
        return _result(
            '{"web_url":"https://gitlab.com/acme/app/-/merge_requests/123#note_789"}'
        )

    state = _state(pr="https://gitlab.com/acme/app/-/merge_requests/123")

    assert (
        post_or_update_review_summary_comment(state, _review_result(), runner=runner)
        == "https://gitlab.com/acme/app/-/merge_requests/123#note_789"
    )
    assert calls[1][:3] == [
        "glab",
        "api",
        "projects/acme%2Fapp/merge_requests/123/notes/789",
    ]
    assert "PUT" in calls[1]


def _state(pr: str | None = None, review_head: str | None = None) -> LaneState:
    return LaneState(
        schema=1,
        id="login",
        status="active",
        branch="fix/login",
        base="main",
        path=Path("/workspace"),
        spec="login",
        review="approve",
        review_head=review_head,
        pr=pr,
    )


def _verification() -> VerifyResult:
    return VerifyResult(
        command=VerifyCommand(argv=["just", "verify"], label="just verify"),
        exit_status=0,
        summary="ok",
    )


def _review_result() -> ReviewResult:
    return ReviewResult(
        review="approve",
        missing_agents=(),
        runs=(
            ReviewRun(
                agent="lane-review-quality",
                paseo_agent_id="agent-1",
                exit_status=0,
                output="Verdict: approve",
            ),
        ),
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
